#!/usr/bin/python
# -*- coding: utf-8 -*-

# This simple example script downloads and processes
# the latest Wikidata dumps to create statistics about
# edit activity. Results are stored in a subdirectory
# results (basic statistics are also reported to the
# console).

import includes.datafetcher as datafetcher
import includes.processdump as processdump
import includes.processinghelper as processinghelper
import includes.logging as logging
import includes.revisionprocessor as revisionprocessor
import includes.rpedits as rpedit
import os

# Define which processing should happen on the data:
dp = processdump.DumpProcessor()
ph = processinghelper.ProcessingHelper() # Collects common helper functions for processing dumps

dp.registerProcessor(revisionprocessor.RPStats()) # Gather basic statistics
rpedcount = rpedit.RPEditCount(ph) # Count edits by day and edits by user
dp.registerProcessor(rpedcount)
#dp.registerProcessor(revisionprocessor.RPDebugLogger()) # Only for debugging

# Iterate through all daily dumps, newest first:
df = datafetcher.DataFetcher()
for daily in df.getNewerDailyDates() :
	logging.log('Analysing daily ' + daily + ' ...')
	file = df.getDailyFile(daily)
	dp.processFile(file)
	file.close()

# Finally also process the latest main dump:
logging.log('Analysing latest dump ' + df.getLatestDumpDate() + ' ...')
file = df.getLatestDumpFile()
dp.processFile(file)
file.close()

### For testing: just do one fixed daily (needs to be downloaded first if not recent)
#file = df.getDailyFile("20130531")
#dp.processFile(file)
#file.close()

## Store detailed results in files in the results directory:
os.chdir(os.path.dirname(os.path.realpath(__file__))) # change back into our base directory if needed
if not os.path.exists('results') :
	os.makedirs('results')
os.chdir('results')
edits = open('edits.csv', 'w')
rpedcount.writeResults(edits)
edits.close()
useredits = open('editsByUser.csv', 'w')
rpedcount.writeEditsByUser(useredits)
useredits.close()
cdBase()



