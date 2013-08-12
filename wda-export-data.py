#!/usr/bin/python
# -*- coding: utf-8 -*-

# This simple example script downloads and processes
# the latest Wikidata dumps to export the data in other
# formats (e.g., RDF). Results are stored in a subdirectory
# results (basic statistics are also reported to the
# console).

import includes.datafetcher as datafetcher
import includes.processdump as processdump
import includes.processinghelper as processinghelper
import includes.logging as logging
import includes.revisionprocessor as revisionprocessor
import includes.rplatest
import includes.epKbFileWriter, includes.epTurtleFileWriter, includes.entityDataFilter
import os, gzip
import argparse

## Process command line arguments:

parser = argparse.ArgumentParser(description='Download Wikidata dump files and write data in another format.')

parser.add_argument('-e', '--export', metavar='FORMAT', nargs='+', type=str,\
		choices=['turtle', 'turtle-stats', 'turtle-links', 'turtle-labels', 'kb'],\
		required=True, help='list of export formats to be used')
parser.add_argument('--offline', dest='offlineMode', action='store_const',\
		const=True, default=False,\
		help='use only previously downloaded files (default: get most recent data)')
parser.add_argument('-l', '--lang', nargs='+', type=str, default=True,\
		help='restrict exported labels etc. to specified language codes (default: no extra restriction)')
parser.add_argument('-s', '--sites', metavar='ID', nargs='+', type=str, default=True,\
		help='restrict exported links to specified site ids (default: no extra restriction)')
parser.add_argument('--datatypes', metavar='TYPE', nargs='+', type=str, default=True,\
		help='restrict exported data etc. to properties with the specified Wikidata types (default: no extra restriction)')
parser.add_argument('--no-refs', dest='includeRefs', action='store_const',\
		const=False, default=True,\
		help='omit references in statements (default: include them)')
parser.add_argument('--no-current', dest='useCurrent', action='store_const',\
		const=False, default=True,\
		help='work with dumps containing all revisions (default: use dumps that contain only current revisions)')
parser.add_argument('--max-date', metavar='YYYYMMDD', dest='maxDate', type=str, default=True,\
		help='only consider dumps up to this date (default: consider all dumps up to now); note that older (daily) dumps may no longer be available online')

args = parser.parse_args()

#print str(args.export)
#exit(1)

## Store detailed results in files in the results directory:
os.chdir(os.path.dirname(os.path.realpath(__file__))) # change back into our base directory if needed
if not os.path.exists('results') :
	os.makedirs('results')

## Fetch and process data:
df = datafetcher.DataFetcher(args.offlineMode,args.useCurrent)
if args.maxDate != True:
	df.setMaxDumpDate(args.maxDate)
curdate = df.getLatestDate()

# Define which processing should happen on the data:
dp = processdump.DumpProcessor()
ph = processinghelper.ProcessingHelper() # Collects common helper functions for processing dumps

dp.registerProcessor(revisionprocessor.RPStats()) # Gather basic statistics

rplatest = includes.rplatest.RPLatest(ph) # process latest revisions of all entities
dp.registerProcessor(rplatest)

for ef in args.export:

	dataFilter = includes.entityDataFilter.EntityDataFilter()
	dataFilter.setIncludeLanguages(args.lang)
	dataFilter.setIncludeSites(args.sites)
	dataFilter.setIncludeReferences(args.includeRefs)
	dataFilter.setIncludePropertyTypes(args.datatypes)
	extraName = ''

	if ef == 'turtle':
		if args.lang != True or args.sites != True or args.datatypes != True or args.includeRefs == False:
			extraName = '-' + dataFilter.getHashCode()
		filename = 'results/turtle-' + curdate + extraName + '.ttl.gz'
		logging.log('Exporting Turtle to file ' + filename)
		turtleFile = gzip.open(filename, 'w')
		epTurtle = includes.epTurtleFileWriter.EPTurtleFile(turtleFile,dataFilter)
		rplatest.registerEntityProcessor(epTurtle)
	elif ef == 'turtle-stats':
		dataFilter.setIncludeLanguages([])
		dataFilter.setIncludeSites([])
		if args.datatypes != True or args.includeRefs == False:
			extraName = '-' + dataFilter.getHashCode()
		filename = 'results/turtle-' + curdate + '-statements' + extraName + '.ttl.gz'
		logging.log('Exporting Turtle (statements only) to file ' + filename)
		turtleFile = gzip.open(filename, 'w')
		epTurtle = includes.epTurtleFileWriter.EPTurtleFile(turtleFile,dataFilter)
		rplatest.registerEntityProcessor(epTurtle)
	elif ef == 'turtle-links':
		dataFilter.setIncludeLanguages([])
		dataFilter.setIncludeStatements(False)
		if args.sites != True:
			extraName = '-' + dataFilter.getHashCode()
		filename = 'results/turtle-' + curdate + '-links' + extraName + '.ttl.gz'
		logging.log('Exporting Turtle (links only) to file ' + filename)
		turtleFile = gzip.open(filename, 'w')
		epTurtle = includes.epTurtleFileWriter.EPTurtleFile(turtleFile,dataFilter)
		rplatest.registerEntityProcessor(epTurtle)
	elif ef == 'turtle-labels':
		dataFilter.setIncludeSites([])
		dataFilter.setIncludeStatements(False)
		if args.lang != True:
			extraName = '-' + dataFilter.getHashCode()
		filename = 'results/turtle-' + curdate + '-labels' + extraName + '.ttl.gz'
		logging.log('Exporting Turtle (labels etc. only) to file ' + filename)
		turtleFile = gzip.open(filename, 'w')
		epTurtle = includes.epTurtleFileWriter.EPTurtleFile(turtleFile,dataFilter)
		rplatest.registerEntityProcessor(epTurtle)
	elif ef == 'kb':
		# TODO no support for filtering right now
		filename = 'results/kb-' + curdate + '.txt.gz'
		logging.log('Exporting KB format to file ' + filename)
		kbFile = gzip.open(filename, 'w')
		epKb = includes.epKbFileWriter.EPKbFile(kbFile)
		rplatest.registerEntityProcessor(epKb)
	else:
		logging.log('*** Warning: unsupported export format "' + ef + '"')

#rpedcount = rpedit.RPEditCount(ph) # Count edits by day and edits by user
#dp.registerProcessor(rpedcount)
#dp.registerProcessor(revisionprocessor.RPDebugLogger()) # Only for debugging

# Iterate through all dumps, newest first:
df.processRecentDumps(dp)

rplatest.close()




