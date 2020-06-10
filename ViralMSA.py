#! /usr/bin/env python3
'''
ViralMSA: Reference-guided multiple sequence alignment of viral genomes
'''

# imports
from Bio import Entrez
from datetime import datetime
from json import load as jload
from math import log2
from multiprocessing import cpu_count
from os import chdir,getcwd,makedirs,remove
from os.path import abspath,expanduser,isdir,isfile,split
from shutil import move
from subprocess import call,check_output,PIPE,Popen,STDOUT
from sys import argv,stderr,stdout
from urllib.request import urlopen
import argparse

# useful constants
VERSION = '1.0.2'
RELEASES_URL = 'https://api.github.com/repos/niemasd/ViralMSA/tags'
CIGAR_LETTERS = {'M','D','I','S','H','=','X'}

# reference genomes for common viruses
REFS = {
    'bombalivirus':    'NC_039345', # Bombali Virus (Bombali ebolavirus)
    'bundibugyovirus': 'NC_014373', # Bundibugyo Virus (Bundibugyo ebolavirus)
    'hcv1':            'NC_004102', # HCV genotype 1
    'hcv1h77':         'NC_038882', # HCV genotpye 1 (isolate H77)
    'hcv2':            'NC_009823', # HCV genotype 2
    'hcv3':            'NC_009824', # HCV genotype 3
    'hcv4':            'NC_009825', # HCV genotype 4
    'hcv5':            'NC_009826', # HCV genotype 5
    'hcv6':            'NC_009827', # HCV genotype 6
    'hcv7':            'NC_030791', # HCV genotype 7
    'hiv1':            'NC_001802', # HIV-1
    'hiv2':            'NC_001722', # HIV-2
    'ebolavirus':      'NC_002549', # Ebola Virus (Zaire ebolavirus)
    'restonvirus':     'NC_004161', # Reston Virus (Reston ebolavirus)
    'sarscov2':        'MT072688',  # SARS-CoV-2 (COVID-19)
    'sudanvirus':      'NC_006432', # Sudan Virus (Sudan ebolavirus)
    'taiforestvirus':  'NC_014372', # Tai Forest Virus (Tai Forest ebolavirus, Cote d'Ivoire ebolavirus)
}
REF_NAMES = {
    'Ebola': {
        'bombalivirus':    'Bombali Virus (Bombali ebolavirus)',
        'bundibugyovirus': 'Bundibugyo Virus (Bundibugyo ebolavirus)',
        'ebolavirus':      'Ebola Virus (Zaire ebolavirus)',
        'restonvirus':     'Reston Virus (Reston ebolavirus)',
        'sudanvirus':      'Sudan Virus (Sudan ebolavirus)',
        'taiforestvirus':  'Tai Forest Virus (Tai Forest ebolavirus, Cote d\'Ivoire ebolavirus)',
    },

    'HCV': {
        'hcv1':            'HCV genotype 1',
        'hcv1h77':         'HCV genotpye 1 (isolate H77)',
        'hcv2':            'HCV genotype 2',
        'hcv3':            'HCV genotype 3',
        'hcv4':            'HCV genotype 4',
        'hcv5':            'HCV genotype 5',
        'hcv6':            'HCV genotype 6',
        'hcv7':            'HCV genotype 7',
    },
    
    'HIV': {
        'hiv1':            'HIV-1',
    },
    
    'SARS-CoV-2': {
        'sarscov2':        'SARS-CoV-2 (COVID-19)',
    }
}

# print to long (prefixed by current time)
def print_log(s='', end='\n'):
    print("[%s] %s" % (get_time(), s), end=end); stdout.flush()

# convert a ViralMSA version string to a tuple of integers
def parse_version(s):
    return tuple(int(v) for v in s.split('.'))

# update ViralMSA to the newest version
def update_viralmsa():
    tags = jload(urlopen(RELEASES_URL))
    newest = max(tags, key=lambda x: parse_version(x['name']))
    if parse_version(newest['name']) <= parse_version(VERSION):
        print("ViralMSA is already at the newest version (%s)" % VERSION); exit(0)
    old_version = VERSION; new_version = newest['name']
    url = 'https://raw.githubusercontent.com/niemasd/ViralMSA/%s/ViralMSA.py' % newest['commit']['sha']
    content = urlopen(url).read()
    with open(__file__, 'wb') as f:
        f.write(content)
    print("Successfully updated ViralMSA %s --> %s" % (old_version, new_version)); exit(0)

# return the current time as a string
def get_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# parse a CIGAR string
def parse_cigar(s):
    out = list(); ind = len(s)-1
    while ind >= 0:
        let = s[ind]; ind -= 1; num = ''
        while s[ind] not in CIGAR_LETTERS:
            num += s[ind]; ind -= 1
        out.append((let, int(num[::-1])))
    return out[::-1]

# check minimap2
def check_minimap2():
    try:
        o = check_output(['minimap2', '-h'])
    except:
        o = None
    if o is None or 'Usage: minimap2' not in o.decode():
        print("ERROR: Minimap2 is not runnable in your PATH", file=stderr); exit(1)

# check bowtie2
def check_bowtie2():
    try:
        o = check_output(['bowtie2', '-h'])
    except:
        o = None
    if o is None or 'Bowtie 2 version' not in o.decode():
        print("ERROR: bowtie2 is not runnable in your PATH", file=stderr); exit(1)
    try:
        o = check_output(['bowtie2-build', '-h'])
    except:
        o = None
    if o is None or 'Bowtie 2 version' not in o.decode():
        print("ERROR: bowtie2-build is not runnable in your PATH", file=stderr); exit(1)

# check HISAT2
def check_hisat2():
    try:
        o = check_output(['hisat2', '-h'])
    except:
        o = None
    if o is None or 'HISAT2 version' not in o.decode():
        print("ERROR: hisat2 is not runnable in your PATH", file=stderr); exit(1)
    try:
        o = check_output(['hisat2-build', '-h'])
    except:
        o = None
    if o is None or 'HISAT2 version' not in o.decode():
        print("ERROR: hisat2-build is not runnable in your PATH", file=stderr); exit(1)

# check STAR
def check_star():
    try:
        o = check_output(['STAR', '-h'])
    except:
        o = None
    if o is None or 'Usage: STAR' not in o.decode():
        print("ERROR: STAR is not runnable in your PATH", file=stderr); exit(1)

# build minimap2 index
def build_index_minimap2(ref_genome_path, threads, verbose=True):
    index_path = '%s.mmi' % ref_genome_path
    if isfile(index_path):
        if verbose:
            print_log("Minimap2 index found: %s" % index_path)
        return
    command = ['minimap2', '-t', str(threads), '-d', index_path, ref_genome_path]
    if verbose:
        print_log("Building Minimap2 index: %s" % ' '.join(command))
    log = open('%s.log' % index_path, 'w'); call(command, stderr=log); log.close()
    if verbose:
        print_log("Minimap2 index built: %s" % index_path)

# build bowtie2 index
def build_index_bowtie2(ref_genome_path, threads, verbose=True):
    exts = ['1.bt2', '2.bt2', '3.bt2', '4.bt2', 'rev.1.bt2', 'rev.2.bt2']
    all_found = True
    for ext in exts:
        if not isfile('%s.bowtie2.%s' % (ref_genome_path,ext)):
            all_found = False; break
    if all_found:
        if verbose:
            print_log("bowtie2 index found: %s.bowtie2.*.bt2" % ref_genome_path)
        return
    for ext in exts:
        if isfile('%s.bowtie2.%s' % (ref_genome_path,ext)):
            remove('%s.bowtie2.%s' % (ref_genome_path,ext))
    ref_genome_dir, ref_genome_fn = split(ref_genome_path)
    orig_dir = getcwd()
    chdir(ref_genome_dir)
    command = ['bowtie2-build', '--threads', str(threads), ref_genome_path, '%s.bowtie2' % ref_genome_fn]
    if verbose:
        print_log("Building bowtie2 index: %s" % ' '.join(command))
    log = open('%s.bowtie2.log' % ref_genome_path, 'w'); call(command, stdout=log, stderr=STDOUT); log.close()
    if verbose:
        print_log("bowtie2 index built: %s.bowtie2.*.bt2" % ref_genome_path)
    chdir(orig_dir)

# build HISAT2 index
def build_index_hisat2(ref_genome_path, threads, verbose=True):
    exts = [('%d.ht2'%i) for i in range(1,9)]
    all_found = True
    for ext in exts:
        if not isfile('%s.hisat2.%s' % (ref_genome_path,ext)):
            all_found = False; break
    if all_found:
        if verbose:
            print_log("HISAT2 index found: %s.hisat2.*.ht2" % ref_genome_path)
        return
    for ext in exts:
        if isfile('%s.hisat2.%s' % (ref_genome_path,ext)):
            remove('%s.hisat2.%s' % (ref_genome_path,ext))
    ref_genome_dir, ref_genome_fn = split(ref_genome_path)
    orig_dir = getcwd()
    chdir(ref_genome_dir)
    command = ['hisat2-build', '--threads', str(threads), ref_genome_path, '%s.hisat2' % ref_genome_fn]
    if verbose:
        print_log("Building HISAT2 index: %s" % ' '.join(command))
    log = open('%s.hisat2.log' % ref_genome_path, 'w'); call(command, stdout=log, stderr=STDOUT); log.close()
    if verbose:
        print_log("HISAT2 index built: %s.hisat2.*.ht2" % ref_genome_path)
    chdir(orig_dir)

# build STAR index
def build_index_star(ref_genome_path, threads, verbose=True):
    delete_log = True # STAR by default creates Log.out in the running directory
    if isfile('Log.out'):
        delete_log = False # don't delete it (it existed before running ViralMSA)
    index_path = '%s.STAR' % ref_genome_path
    genome_length = sum(len(l.strip()) for l in open(ref_genome_path) if not l.startswith('>'))
    genomeSAindexNbases = min(14, int(log2(genome_length)/2)-1)
    makedirs(index_path, exist_ok=True)
    command = ['STAR', '--runMode', 'genomeGenerate', '--runThreadN', str(threads), '--genomeDir', index_path, '--genomeFastaFiles', ref_genome_path, '--genomeSAindexNbases', str(genomeSAindexNbases)]
    if verbose:
        print_log("Building STAR index: %s" % ' '.join(command))
    log = open('%s/index.log' % index_path, 'w'); call(command, stdout=log, stderr=STDOUT); log.close()
    if verbose:
        print_log("STAR index built: %s" % index_path)
    if delete_log and isfile('Log.out'):
        remove('Log.out')

# align genomes using minimap2
def align_minimap2(seqs_path, out_sam_path, ref_genome_path, threads, verbose=True):
    index_path = '%s.mmi' % ref_genome_path
    command = ['minimap2', '-t', str(threads), '-a', '-o', out_sam_path, index_path, seqs_path]
    if verbose:
        print_log("Aligning using Minimap2: %s" % ' '.join(command))
    log = open('%s.log' % out_sam_path, 'w'); call(command, stderr=log); log.close()
    if verbose:
        print_log("Minimap2 alignment complete: %s" % out_sam_path)

# align genomes using bowtie2
def align_bowtie2(seqs_path, out_sam_path, ref_genome_path, threads, verbose=True):
    command = ['bowtie2', '--very-sensitive', '-p', str(threads), '-f', '-x', '%s.bowtie2' % ref_genome_path, '-U', seqs_path, '-S', out_sam_path]
    if verbose:
        print_log("Aligning using bowtie2: %s" % ' '.join(command))
    log = open('%s.log' % out_sam_path, 'w'); call(command, stderr=log); log.close()
    if verbose:
        print_log("bowtie2 alignment complete: %s" % out_sam_path)

# align genomes using HISAT2
def align_hisat2(seqs_path, out_sam_path, ref_genome_path, threads, verbose=True):
    command = ['hisat2', '--very-sensitive', '-p', str(threads), '-f', '-x', '%s.hisat2' % ref_genome_path, '-U', seqs_path, '-S', out_sam_path]
    if verbose:
        print_log("Aligning using HISAT2: %s" % ' '.join(command))
    log = open('%s.log' % out_sam_path, 'w'); call(command, stderr=log); log.close()
    if verbose:
        print_log("HISAT2 alignment complete: %s" % out_sam_path)

# align genomes using STAR
def align_star(seqs_path, out_sam_path, ref_genome_path, threads, verbose=True):
    delete_log = True # STAR by default creates Log.out in the running directory
    if isfile('Log.out'):
        delete_log = False # don't delete it (it existed before running ViralMSA)
    index_path = '%s.STAR' % ref_genome_path
    out_sam_dir, out_sam_fn = split(out_sam_path)
    out_file_prefix = '%s.' % '.'.join(out_sam_path.split('.')[:-1])
    command = ['STAR', '--runThreadN', str(threads), '--genomeDir', index_path, '--readFilesIn', seqs_path, '--outFileNamePrefix', out_file_prefix, '--outFilterMismatchNmax', '9999999999']
    if verbose:
        print_log("Aligning using STAR: %s" % ' '.join(command))
    log = open('%s/STAR.log' % out_sam_dir, 'w'); call(command, stdout=log); log.close()
    move('%sAligned.out.sam' % out_file_prefix, out_sam_path)
    if verbose:
        print_log("STAR alignment complete: %s" % out_sam_dir)
    if delete_log and isfile('Log.out'):
        remove('Log.out')

# aligners
ALIGNERS = {
    'bowtie2': {
        'check':       check_bowtie2,
        'build_index': build_index_bowtie2,
        'align':       align_bowtie2,
    },

    'hisat2': {
        'check':       check_hisat2,
        'build_index': build_index_hisat2,
        'align':       align_hisat2,
    },

    'minimap2': {
        'check':       check_minimap2,
        'build_index': build_index_minimap2,
        'align':       align_minimap2,
    },

    'star': {
        'check':       check_star,
        'build_index': build_index_star,
        'align':       align_star,
    },
}

# main content
if __name__ == "__main__":
    # check if user wants to update ViralMSA
    if '-u' in argv or '--update' in argv:
        update_viralmsa()

    # check if user just wants to list references
    if '-l' in argv or '--list_references' in argv:
        print("=== List of ViralMSA Reference Sequences ===")
        for v in sorted(REF_NAMES.keys()):
            print("* %s" % v)
            for r in sorted(REF_NAMES[v].keys()):
                print("  - %s: %s" % (r, REF_NAMES[v][r]))
        exit(0)

    # parse user args
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-s', '--sequences', required=True, type=str, help="Input Sequences (FASTA format)")
    parser.add_argument('-r', '--reference', required=True, type=str, help="Reference")
    parser.add_argument('-e', '--email', required=True, type=str, help="Email Address (for Entrez)")
    parser.add_argument('-o', '--output', required=True, type=str, help="Output Directory")
    parser.add_argument('-a', '--aligner', required=False, type=str, default='Minimap2', help="Aligner")
    parser.add_argument('-t', '--threads', required=False, type=int, default=cpu_count(), help="Number of Threads")
    parser.add_argument('-l', '--list_references', action="store_true", help="List all reference sequences")
    parser.add_argument('--omit_ref', action="store_true", help="Omit reference sequence from output alignment")
    parser.add_argument('--viralmsa_dir', required=False, type=str, default=abspath(expanduser("~/.viralmsa")), help="ViralMSA Cache Directory")
    args = parser.parse_args()
    if args.threads < 1:
        print("ERROR: Number of threads must be positive", file=stderr); exit(1)
    args.aligner = args.aligner.lower()
    if args.aligner not in ALIGNERS:
        print("ERROR: Invalid aligner: %s (valid options: %s)" % (args.aligner, ', '.join(sorted(ALIGNERS.keys()))), file=stderr); exit(1)
    ALIGNERS[args.aligner]['check']()
    args.sequences = abspath(expanduser(args.sequences))
    if not isfile(args.sequences):
        print("ERROR: Sequences file not found: %s" % args.sequences, file=stderr); exit(1)
    if args.sequences.lower().endswith('.gz'):
        print("ERROR: Sequences cannot be compressed: %s" % args.sequences, file=stderr); exit(1)
    input_IDs = {l.strip()[1:] for l in open(args.sequences) if l.startswith('>')}
    args.output = abspath(expanduser(args.output))
    if isdir(args.output) or isfile(args.output):
        print("ERROR: Output directory exists: %s" % args.output, file=stderr); exit(1)
    tmp = args.reference.lower().replace(' ','').replace('-','').replace('_','')
    if tmp in REFS:
        args.reference = REFS[tmp]
    args.reference = args.reference.upper()
    makedirs(args.viralmsa_dir, exist_ok=True)

    # print run information
    print_log("===== RUN INFORMATION =====")
    print_log("ViralMSA Version: %s" % VERSION)
    print_log("Sequences: %s" % args.sequences)
    print_log("Reference: %s" % args.reference)
    print_log("Email Address: %s" % args.email)
    print_log("Output Directory: %s" % args.output)
    print_log("Aligner: %s" % args.aligner)
    print_log("ViralMSA Cache Directory: %s" % args.viralmsa_dir)
    print_log()

    # download reference genome if not already downloaded
    print_log("===== REFERENCE GENOME =====")
    ref_path = '%s/%s' % (args.viralmsa_dir, args.reference)
    ref_genome_path = '%s/%s.fas' % (ref_path, args.reference)
    makedirs(ref_path, exist_ok=True)
    if isfile(ref_genome_path):
        print_log("Reference genome found: %s" % ref_genome_path)
    else:
        print_log("Downloading reference genome from NCBI...")
        Entrez.email = args.email
        handle = Entrez.efetch(db='nucleotide', rettype='fasta', id=args.reference)
        seq = handle.read()
        if seq.count('>') != 1:
            print("ERROR: Reference genome must only have a single sequence", file=stderr); exit(1)
        f = open(ref_genome_path, 'w'); f.write(seq.strip()); f.write('\n'); f.close()
        print_log("Reference genome downloaded: %s" % ref_genome_path)

    # build aligner index (if needed)
    ALIGNERS[args.aligner]['build_index'](ref_genome_path, args.threads)
    print_log()

    # align viral genomes against referencea
    print_log("===== ALIGNMENT =====")
    out_sam_path = '%s/%s.sam' % (args.output, args.sequences.split('/')[-1])
    makedirs(args.output)
    ALIGNERS[args.aligner]['align'](args.sequences, out_sam_path, ref_genome_path, args.threads)

    # convert SAM to MSA FASTA
    print_log("Converting SAM to FASTA...")
    out_aln_path = '%s/%s.aln' % (args.output, args.sequences.split('/')[-1])
    aln = open(out_aln_path, 'w'); ref_seq = list()
    for line in open(ref_genome_path):
        l = line.strip()
        if len(l) == 0:
            continue
        if l[0] != '>':
            ref_seq.append(l)
        elif not args.omit_ref:
            aln.write(l); aln.write('\n')
    ref_seq = ''.join(ref_seq)
    if not args.omit_ref:
        aln.write(ref_seq); aln.write('\n')
    output_IDs = set()
    for line in open(out_sam_path):
        l = line.rstrip('\n')
        if len(l) == 0 or l[0] == '@':
            continue
        parts = l.split('\t')
        flags = int(parts[1])
        if flags != 0 and flags != 16:
            continue
        ID = parts[0].strip(); output_IDs.add(ID)
        ref_ind = int(parts[3])-1
        cigar = parts[5].strip()
        seq = parts[9].strip()
        edits = parse_cigar(cigar)
        aln.write('>'); aln.write(ID); aln.write('\n')
        if ref_ind > 0:
            aln.write('-'*ref_ind) # write gaps before alignment
        ind = 0; seq_len = ref_ind
        for e, e_len in edits:
            if e == 'M' or e == '=' or e == 'X': # (mis)match)
                aln.write(seq[ind:ind+e_len]); ind += e_len; seq_len += e_len
            elif e == 'D':                       # deletion (gap in query)
                aln.write('-'*e_len); seq_len += e_len
            elif e == 'I':                       # insertion (gap in reference; ignore)
                ind += e_len
            elif e == 'S' or e == 'H':           # starting/ending segment of query not in reference (i.e., span of insertions; ignore)
                ind += e_len
        if seq_len < len(ref_seq):
            aln.write('-'*(len(ref_seq)-seq_len)) # write gaps after alignment
        aln.write('\n')
    aln.close()
    print_log("Multiple sequence alignment complete: %s" % out_aln_path)
    if len(output_IDs) < len(input_IDs):
        print_log("WARNING: Some sequences from the input are missing from the output. Perhaps try a different aligner?")
