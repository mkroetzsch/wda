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

parser.add_argument('--offline', dest='offlineMode', action='store_const',\
		const=True, default=False,\
		help='use only previously downloaded files (default: get most recent data)')

args = parser.parse_args()

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

dataFilter = includes.entityDataFilter.EntityDataFilter()
dataFilter.setIncludeLanguages(['en','de','fr'])
dataFilter.setIncludeSites(['enwiki','dewiki','enwikivoyage','zhwiki','fawiki'])

## Uncommment to create "KB" format file
#kbFile = gzip.open('results/kb-' + curdate + '.txt.gz', 'w')
#epKb = includes.epKbFileWriter.EPKbFile(kbFile)
#rplatest.registerEntityProcessor(epKb)

turtleFile = gzip.open('results/turtle-' + curdate + '.txt.gz', 'w')
epTurtle = includes.epTurtleFileWriter.EPTurtleFile(turtleFile,dataFilter)
rplatest.registerEntityProcessor(epTurtle)

#rpedcount = rpedit.RPEditCount(ph) # Count edits by day and edits by user
#dp.registerProcessor(rpedcount)
#dp.registerProcessor(revisionprocessor.RPDebugLogger()) # Only for debugging

# Iterate through all dumps, newest first:
df.processRecentDumps(dp)

kbFile.close()
turtleFile.close()



