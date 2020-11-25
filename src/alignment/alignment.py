from src.scoring import scoring
from src.objects import Spectrum, SequenceAlignment, HybridSequenceAlignment, Database, Alignments, DEVFallOffEntry
from src.alignment import alignment_utils, hybrid_alignment

from src import utils
from src import database
from src import gen_spectra

import math
import re

####################### Time constants #######################

import time
TIME_LOG_FILE = './timelog.txt'

# to keep track of the time each step takes
FILTER_TIME = 0
FIRST_ALIGN_TIME = 0
AMBIGUOUS_REMOVAL_TIME = 0
PRECURSOR_MASS_TIME = 0
OBJECTIFY_TIME = 0

# keep track of frequency
FILTER_COUNT = 0
FIRST_ALIGN_COUNT = 0
AMBIGUOUS_REMOVAL_COUNT = 0
PRECURSOR_MASS_COUNT = 0
OBJECTIFY_COUNT = 0

####################### Public functions #######################

def same_protein_alignment(seq1: str, seq2: str, parent_sequence: str) -> (str, str):
    '''
    Attempt to create a non-hybrid alignment from two sequences from the same protein. If the 
    two sequences do not directly overlap but have <= 1% (or 1 if very short) of the total number 
    of amino acids, make the alignment. If not, create a hybrid alignment from that. If one 
    compeletely overlaps the other, use that as the alignment. 
    
    Example 1: Overlapped sequences
        seq1: CDE        starting position: 2
        seq2: ABCDEFG    starting position: 0
        
        Output: (ABCDEFG, None)
        
    Example 2: Partial overlaping sequences
        seq1: ABCDE      starting position: 0
        seq2: DEFGH      starting position: 3
        
        Outputs: (ABCDEFGH, None)
        
    Example 3: Non overlapping within the 1% (or 1)
        seq1: ABCDE      starting position: 0
        seq2: GHIJK      starting position: 6
        
        protein length: 52
        grace length = max(1, 1% of 52) = 1
        
        Outputs: (ABCDEFGHIJK, None)
        
    Example 4: Theoretical overlap but outside of range
        seq1: ABCDE      starting position: 0
        seq2: EFGHI      starting position: 30
        
        outside of allowed range, make hybrid
        
        Outputs: (ABCDEFGHI, ABCD(E)FGHI)
        
    
    Inputs:
        seq1:            (str) left sequence to align
        seq2:            (str) right sequence to align
        parent_sequence: (str) sequence of the shared parent protein
    Outputs:
        tuple:   first entry is the seqence, second entry is 
                 the second entry is the hybrid sequence, if not hybrid, then its None
    ''' 
    # check to see if they are equal or one covers the entirety of the other
    if seq1 == seq2:
        return (seq1, None)
    
    if seq1 in seq2:
        return (seq2, None)
    
    if seq2 in seq1: 
        return (seq1, None)
    
    # get the number of gap amino acids allowed
    gap_aa = max(1, len(parent_sequence) // 100)
    
    # get the positions of the left sequence from the protein
    left_start = [m.start() for m in re.finditer(seq1, parent_sequence)]
    
    # get the positions of the right sequence from the protein
    right_start = [m.start() for m in re.finditer(seq2, parent_sequence)]
    
    # if EVERY position of seq1 is to the RIGHT of ALL positions of seq2, make a hybrid 
    if all([r < l for r in right_start for l in left_start]):
        return hybrid_alignment.hybrid_alignment(seq1, seq2)
    
    # check to see if any of the points are within the gap_aa limit
    nonhybrid_alignments = []

    for l in left_start:
        for r in right_start:
            
            # if the right is to the left of left, continue
            if r < l:
                continue
                
            # if the right start - left start plus the length of the subsequence 
            # is less than the gap, just take the starting position of l and ending position 
            # of seq2 to make the full alignment
            if r - (l + len(seq1)) <= gap_aa:
                overlapped = parent_sequence[l: r + len(seq2)]
                nonhybrid_alignments.append(overlapped)
        
    # if no nonhybrids could be made, return a hybrid alignment
    if len(nonhybrid_alignments) == 0:
        return hybrid_alignment.hybrid_alignment(seq1, seq2)
    
    # we have at least one good one. Return the shortest one
    nonhybrid_alignments.sort(key=lambda x: len(x))
    return (nonhybrid_alignments[0], None)

def align_b_y(b_results: list, y_results: list, spectrum: Spectrum, db: Database) -> list:
    '''
    Take 2 lists of sequences: one from the N terminus side (b_results) and 
    one from the C terminus side (y_results). Lookup the sequences in the database.
    If the two sequences are from the same protein, try and overlap the two strings.
    If there is an overlap, return it. In all other situations, a hybrid alignment is
    returned instead.

    Inputs:
        b_results:  (list of str) sequences found from b hits
        y_results:  (list of str) sequences fround from y hits
        spectrum:   (Spectrum) observed
        db:         (Database) source of the sequences
    Outputs:
        (list) tuples of aligned sequences. First entry is the nonhybrid, second (if hybrid)
                has the hybrid characters -(). If not hybrid, it is None
    '''
    # try and create an alignment from each extended b and y ion sequence
    spec_alignments = []
    #[item for sublist in t for item in sublist]
    for seq in b_results:
        spec_alignments += [(x, None) for x in alignment_utils.extend_non_hybrid(seq, spectrum, 'b', db)]
    for seq in y_results:
        spec_alignments += [(x, None) for x in alignment_utils.extend_non_hybrid(seq, spectrum, 'y', db)]

    for b_seq in b_results:

        # get all the b proteins
        b_proteins = database.get_proteins_with_subsequence(db, b_seq)

        for y_seq in y_results:

            # ge the y proteins
            y_proteins = database.get_proteins_with_subsequence(db, y_seq)
            
            # the sequence is from the same protein, try and overlap it
            if any([x in y_proteins for x in b_proteins]):

                # get each protein they have in common
                shared_prots = [x for x in y_proteins if x in b_proteins]
                
                # try each of them 
                for sp in shared_prots:

                    # get the sequence from the entry for alignment
                    prot_seqs = database.get_entry_by_name(db, sp)

                    for prot_entry in prot_seqs:

                        # append any alignments made from these 2 sequences
                        spec_alignments.append(
                            same_protein_alignment(b_seq, y_seq, prot_entry.sequence)
                        )
                
                # try just a dumb hybrid too to make sure
                spec_alignments.append((f'{b_seq}{y_seq}', f'{b_seq}-{y_seq}'))

            # otherwise try hybrid alignment
            else: 
                spec_alignments.append(hybrid_alignment.hybrid_alignment(b_seq, y_seq))
        
    # remove repeats
    return list(set([x for x in spec_alignments if x is not None]))

def attempt_alignment(
    spectrum: Spectrum, 
    db: Database, 
    b_hits: list,
    y_hits: list, 
    n=3, 
    ppm_tolerance=20, 
    precursor_tolerance=1,
    DEBUG=False, 
    is_last=False, 
    truth=None, 
    fall_off=None
) -> Alignments:
    '''
    Given a set of left and right (b and y ion) hits, try and overlap or extend one side to 
    explain the input spectrum

    Example:
        b_hits = [ABCD, LMNOP]
        y_hits = [ABCDEF]
        if the true value of the spectrum is ABCDEF, then we filter out LMNOP,
        overlap ABCD and ABCDEF and return ABCDEF

    Inputs:
        spectrum:               (Spectrum) spectrum to align
        db:                     (Database) Holds protein entries
        hits:                   (KmerMassesResults) hits from the hashing on a KmerMasses object
        base_kmer_len:          (int) minimum length kmer length used for filtering results
    kwargs:
        n:                      (int) number of results to return. Default=3
        ppm_tolerance:          (int) ppm tolerance to allow when scoring. Default=20
        precursor_tolerance:    (float) tolerance in Da to allow for a match. Default = 1
    Outputs:
        (Alignments) attempted alignemnts. Contains both or either of SequenceAlignment and HybridSequenceAlignment
    '''
    global FIRST_ALIGN_TIME, AMBIGUOUS_REMOVAL_TIME, FILTER_TIME, PRECURSOR_MASS_TIME, OBJECTIFY_TIME
    global FIRST_ALIGN_COUNT, AMBIGUOUS_REMOVAL_COUNT, FILTER_COUNT, PRECURSOR_MASS_COUNT, OBJECTIFY_COUNT

    # if we are in dev mode this removes the need for extra long ifs
    DEV = truth is not None and fall_off is not None

    # run the first round of alignments
    st = time.time()
    a = align_b_y(b_hits, y_hits, spectrum, db)

    # if we have truth and fall_off, check for them
    if DEV:
        # we want to make b and y seqs out of the alignments because we want to give the benefit of the doubt
        # since we can fill in precursor
        b_seqs = [x[0] for x in a]
        y_seqs = [x[0] for x in a]

        # get the id, the sequnce, and if its a hybrid
        _id = spectrum.id
        is_hybrid = truth[_id]['hybrid']
        truth_seq = truth[_id]['sequence']

        if not utils.DEV_contains_truth_parts(truth_seq, is_hybrid, b_seqs, y_seqs):

            # add metadata about what what the alignments were
            metadata = {
                'alignments': a, 
                'before_alignments_b': b_seqs, 
                'before_alignments_y': y_seqs
            }

            fall_off[_id] = DEVFallOffEntry(
                is_hybrid, 
                truth_seq, 
                'first_alignment_round', 
                metadata
            )

            # exit the alignment
            return Alignments(spectrum, [])

    FIRST_ALIGN_COUNT += len(a)
    FIRST_ALIGN_TIME += time.time() - st
    DEBUG and print(f'First alignment round took {time.time() - st} time resulting in {len(a)} alignments')

    # get the predicted length of the sequence and allow for a 25% gap to be filled in
    predicted_len = utils.predicted_len(spectrum.precursor_mass, spectrum.precursor_charge)
    allowed_gap = math.ceil(predicted_len * .25)

    # Limit our search to things that match our precursor mass
    # try and fill in the gaps that are in any alignments
    st = time.time()
    precursor_matches = []

    for sequence_pairs in a:
        
        # take the sequence. If hybrid, take the hybrid, otherwise the non hybrid
        sequence = sequence_pairs[0] if sequence_pairs[1] is None else sequence_pairs[1]

        # add the closer precursors to the list
        p_ms = [
            x for x in \
            alignment_utils.fill_in_precursor(spectrum, sequence, db, gap=allowed_gap, tolerance=precursor_tolerance) \
            if x is not None
        ]

        precursor_matches += p_ms

    PRECURSOR_MASS_COUNT += len(precursor_matches)
    PRECURSOR_MASS_TIME += time.time() - st
    DEBUG and print(f'Filling in precursor took {time.time() - st} for {len(a)} sequences')

    # check to see if we no longer have the match. At this point we should
    if DEV:

        # get the id, the sequnce, and if its a hybrid
        _id = spectrum.id
        is_hybrid = truth[_id]['hybrid']
        truth_seq = truth[_id]['sequence']

        if not utils.DEV_contains_truth_exact(truth_seq, is_hybrid, precursor_matches):

            # add metadata about wwhat we had before filling in precursor and 
            # what we ended up after
            metadata = {
                'sequences_before_precursor_filling': a, 
                'sequences_after_precursor_filling': precursor_matches, 
                'observed_precursor_mass': spectrum.precursor_mass, 
                'observed_percursor_charge': spectrum.precursor_charge, 
                'allowed_gap': allowed_gap
            }

            fall_off[_id] = DEVFallOffEntry(
                is_hybrid, 
                truth_seq, 
                'precursor_filling', 
                metadata
            )

            # exit the alignment
            return Alignments(spectrum, [])

    # seperate the hybrids from the non hybrids for later analysis
    nonhyba, hyba = [], []
    for p_m in precursor_matches:

        if '-' in p_m or '(' in p_m or ')' in p_m:
            hyba.append((p_m.replace('-', '').replace('(', '').replace(')', ''), p_m))
        else:
            nonhyba.append((p_m, None))
    
    # replace any hybrid alignments that are seen that can be explained by non 
    # hybrid sequences
    st = time.time()
    updated_hybrids = [] if len(hyba) == 0 else hybrid_alignment.replace_ambiguous_hybrids(hyba, db, spectrum)

    # check to see if we lost the match, but only if the sequence is a hybrid
    if DEV and truth[spectrum.id]['hybrid']:

        # get the id, the sequnce, and if its a hybrid
        _id = spectrum.id
        is_hybrid = truth[_id]['hybrid']
        truth_seq = truth[_id]['sequence']

        # updated hybrids is a list of [(nonhyb, hybrid)]. Do the first value because sometimes the 
        # second value is none because its no longer a hybrid
        if not utils.DEV_contains_truth_exact(truth_seq, is_hybrid, [x[0] for x in updated_hybrids]):

            # add some metadata about what we had before and after ambiguous changing
            metadata = {
                'before_ambiguous_removal': hyba, 
                'after_ambiguous_removal': updated_hybrids
            }

            fall_off[_id] = DEVFallOffEntry(
                is_hybrid, 
                truth_seq, 
                'removing_ambiguous_hybrids', 
                metadata
            )

            # exit the alignment
            return Alignments(spectrum, [])

    AMBIGUOUS_REMOVAL_COUNT += len(updated_hybrids)
    AMBIGUOUS_REMOVAL_TIME += time.time() - st
    DEBUG and print(f'Getting rid of ambiguous time took {time.time() - st}')
 
    # Make alignments into the namedtuple types SpectrumAlignments
    # and HybridSequenceAlignments
    alignments = []
    tracker = {}
    st = time.time()
    for aligned_pair in nonhyba + updated_hybrids:

        # add to tracker, continue if what we see is already in the tracker
        if aligned_pair[0] in tracker:
            continue

        tracker[aligned_pair[0]] = True

        # get the precursor distance. If its too big, continue
        p_d = scoring.precursor_distance(
            spectrum.precursor_mass, 
            gen_spectra.get_precursor(aligned_pair[0], spectrum.precursor_charge)
        )

        # get the final score of these sequences
        b_score = scoring.score_sequence(
            spectrum.spectrum, 
            sorted(gen_spectra.gen_spectrum(aligned_pair[0], ion='b')['spectrum']), 
            ppm_tolerance
        )
        y_score = scoring.score_sequence(
            spectrum.spectrum, 
            sorted(gen_spectra.gen_spectrum(aligned_pair[0], ion='y')['spectrum']), 
            ppm_tolerance
        )

        # the total score for non hybrids will be the sum of the b and y, but hybrids will use 
        # the hybrid score
        t_score = None

        # get the parent proteins of the sequence
        parents = alignment_utils.get_parents(aligned_pair[0] if aligned_pair[1] is None else aligned_pair[1], db)

        # check if the second entry is None
        if aligned_pair[1] is not None:

            # get the hybrid score
            t_score = scoring.hybrid_score(spectrum, aligned_pair[1], ppm_tolerance)

            alignments.append(
                HybridSequenceAlignment(
                    parents[0], 
                    parents[1], 
                    aligned_pair[0], 
                    aligned_pair[1], 
                    b_score, 
                    y_score, 
                    t_score, 
                    p_d
                )
            )

        # if its not a hybrid sequence, make a SequenceAlignment object
        else:
            t_score = b_score + y_score

            alignments.append(
                SequenceAlignment(
                    parents[0], 
                    aligned_pair[0], 
                    b_score, 
                    y_score, 
                    t_score, 
                    p_d
                )
            )
    OBJECTIFY_COUNT += len(nonhyba + updated_hybrids)
    OBJECTIFY_TIME += time.time() - st
    DEBUG and print(f'Time to make into objects took {time.time() - st}')

    # write the time log to file
    if is_last:
        with open(TIME_LOG_FILE, 'w') as o:
            o.write(f'Total result filtering time: {FILTER_TIME}s \t seconds/op: {FILTER_TIME/FILTER_COUNT}s\n')
            o.write(f'B and Y alignment time: {FIRST_ALIGN_TIME}s \t seconds/op: {FIRST_ALIGN_TIME/FIRST_ALIGN_COUNT}s\n')
            o.write(f'Removing ambiguous hybrids time: {AMBIGUOUS_REMOVAL_TIME}s \t seconds/op: {AMBIGUOUS_REMOVAL_TIME/AMBIGUOUS_REMOVAL_COUNT}s\n')
            o.write(f'Matching precursor matches time: {PRECURSOR_MASS_TIME}s \t seconds/op: {PRECURSOR_MASS_TIME/PRECURSOR_MASS_COUNT}s\n')
            o.write(f'Turning matches into objects time: {OBJECTIFY_TIME} \t seconds/op: {OBJECTIFY_TIME/OBJECTIFY_COUNT}\n')

    # get only the top n alignments
    # if all scores are equal, float the non hybrids to the top
    # non hybrid alignment objects have 6 entries, hybrids have 8, so doing 1/len(x) puts non hybrids before hybrids
    sorted_alignments = sorted(
        alignments, 
        key=lambda x: (x.total_score, 1/len(x), x.b_score, x.y_score, 1/x.precursor_distance), 
        reverse=True
    )
    top_n_alignments = sorted_alignments[:n]

    # check to see if we lost the sequence
    if DEV:

        # get the id, the sequnce, and if its a hybrid
        _id = spectrum.id
        is_hybrid = truth[_id]['hybrid']
        truth_seq = truth[_id]['sequence']

        # the sequence is in x.sequence
        if not utils.DEV_contains_truth_exact(truth_seq, is_hybrid, [x.sequence for x in top_n_alignments]):

            # add some metadata about which ones were accepted and which ones werent
            metadata = {
                'top_n': [x._asdict() for x in top_n_alignments], 
                'not_top_n': [x._asdict() for x in sorted_alignments[n:]]
            }

            fall_off[_id] = DEVFallOffEntry(
                is_hybrid, 
                truth_seq, 
                'taking_top_n_alignments', 
                metadata
            )

            # exit the alignment
            return Alignments(spectrum, [])

    return Alignments(
        spectrum, 
        top_n_alignments
    )
