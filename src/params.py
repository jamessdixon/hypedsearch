########################## PROGRAM IO ##########################
# full path to the spectra folder containing all spectra files
SPECTRA_FOLDER = '/Users/zacharymcgrath/Desktop/nod2 data/filteredSpec/'
# full path to the .fasta database file
DATABASE_FILE = '/Users/zacharymcgrath/Desktop/nod2 data/filteredNOD2.fasta'
# full path to the output directory
OUTPUT_DIRECTORY = '/Users/zacharymcgrath/Desktop/Experiment output/filtered_NOD2_E3/'

########################## SEARCH PARAMETERS ##########################
# minimum length peptide to look for
MIN_PEPTIDE_LEN = 3
# maximum length peptide to look for
MAX_PEPTIDE_LEN = 30
# the digest performed on the sample. Current options: [tryptic]
# leave blank if you would like to perform digest-free search
DIGEST = 'tyrptic'
# the number of digest sites that could have been missed
MISSED_CLEAVAGES = 2
# tolerance (in ppm) to allow when matching m/z peaks
PPM_TOLERANCE = 20
# tolerance (in Da) to allow when matching precursor masses
PRECURSOR_TOLERANCE = 3
#-----------------------------------------------------------
# NOTE: when using the filtering options below (either the peak
# filtering or the abundance filtering), only set 1 of the values.
# If both are set, then it defaults to the value set for peak_filter
#-----------------------------------------------------------
# the number of most abundant (intense) peaks to allow when filtering
# input spectra
PEAK_FILTER = 25
# the minimum allowed percentage of the total intensity a peak 
# is allowed to have to pass the filter. Values should be 
# in the range (0, 1) 
RELATIVE_ABUNDANCE_FILTER = 0

########################## RUN PARAMETERS ##########################
# printing to the console during the run
VERBOSE = True
# which scoring algorithm to use. Options are 
# 'ibb', 'ion', 'bb', 'iibb'
SCORING_ALG = 'ion'
# Extra extra printing options for debugging the application
DEBUG = True