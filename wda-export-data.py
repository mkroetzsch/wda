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

args = parser.parse_args()

#print str(args.export)
#exit(1)

## Store detailed results in files in the results directory:
os.chdir(os.path.dirname(os.path.realpath(__file__))) # change back into our base directory if needed
if not os.path.exists('results') :
	os.makedirs('results')

## Fetch and process data:
df = datafetcher.DataFetcher(args.offlineMode)
curdate = df.getLatestDate()

# Define which processing should happen on the data:
dp = processdump.DumpProcessor()
ph = processinghelper.ProcessingHelper() # Collects common helper functions for processing dumps

dp.registerProcessor(revisionprocessor.RPStats()) # Gather basic statistics

rplatest = includes.rplatest.RPLatest(ph) # process latest revisions of all entities
dp.registerProcessor(rplatest)

for ef in args.export:
	if ef == 'turtle':
		dataFilter = includes.entityDataFilter.EntityDataFilter()
		dataFilter.setIncludeLanguages(args.lang)
		dataFilter.setIncludeSites(args.sites)
		turtleFile = gzip.open('results/turtle-' + curdate + '.txt.gz', 'w')
		epTurtle = includes.epTurtleFileWriter.EPTurtleFile(turtleFile,dataFilter)
		rplatest.registerEntityProcessor(epTurtle)
	elif ef == 'turtle-stats':
		dataFilter = includes.entityDataFilter.EntityDataFilter()
		dataFilter.setIncludeLanguages([])
		dataFilter.setIncludeSites([])
		turtleStatsFile = gzip.open('results/turtle-' + curdate + '-statements.txt.gz', 'w')
		epTurtle = includes.epTurtleFileWriter.EPTurtleFile(turtleFile,dataFilter)
		rplatest.registerEntityProcessor(epTurtle)
	elif ef == 'turtle-links':
		dataFilter = includes.entityDataFilter.EntityDataFilter()
		dataFilter.setIncludeLanguages([])
		dataFilter.setIncludeSites(args.sites)
		dataFilter.setIncludeStatements(False)
		turtleFile = gzip.open('results/turtle-' + curdate + '-links.txt.gz', 'w')
		epTurtle = includes.epTurtleFileWriter.EPTurtleFile(turtleFile,dataFilter)
		rplatest.registerEntityProcessor(epTurtle)
	elif ef == 'turtle-labels':
		dataFilter = includes.entityDataFilter.EntityDataFilter()
		dataFilter.setIncludeLanguages(args.lang)
		dataFilter.setIncludeSites([])
		dataFilter.setIncludeStatements(False)
		turtleFile = gzip.open('results/turtle-' + curdate + '-labels.txt.gz', 'w')
		epTurtle = includes.epTurtleFileWriter.EPTurtleFile(turtleFile,dataFilter)
		rplatest.registerEntityProcessor(epTurtle)
	elif ef == 'kb':
		# TODO no support for filtering right now
		kbFile = gzip.open('results/kb-' + curdate + '.txt.gz', 'w')
		epKb = includes.epKbFileWriter.EPKbFile(kbFile)
		rplatest.registerEntityProcessor(epKb)
	else:
		logging.log('*** Warning: unsupported export format "' + ef + '"')

#dataFilter = includes.entityDataFilter.EntityDataFilter()
#dataFilter.setIncludeLanguages(['en','de','fr'])
#dataFilter.setIncludeSites(['enwiki','dewiki','enwikivoyage','zhwiki','fawiki'])

#turtleFile = gzip.open('results/turtle-' + curdate + '.txt.gz', 'w')
#epTurtle = includes.epTurtleFileWriter.EPTurtleFile(turtleFile,dataFilter)
#rplatest.registerEntityProcessor(epTurtle)

#rpedcount = rpedit.RPEditCount(ph) # Count edits by day and edits by user
#dp.registerProcessor(rpedcount)
#dp.registerProcessor(revisionprocessor.RPDebugLogger()) # Only for debugging

# Iterate through all dumps, newest first:
df.processRecentDumps(dp)

rplatest.close()




