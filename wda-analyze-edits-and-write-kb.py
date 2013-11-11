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
import includes.revisionprocessor as revisionprocessor
import includes.rpedits as rpedit
import includes.rpkb as rpkb
import os
import gzip
import io

# Define which processing should happen on the data:
dp = processdump.DumpProcessor()
ph = processinghelper.ProcessingHelper() # Collects common helper functions for processing dumps

dp.registerProcessor(revisionprocessor.RPStats()) # Gather basic statistics
rpedcount = rpedit.RPEditCount(ph) # Count edits by day and edits by user
dp.registerProcessor(rpedcount)
output = io.open('kb.txt', 'w', encoding='utf-8')
kbwriter = rpkb.RPKB(ph,output)
dp.registerProcessor(kbwriter)
#dp.registerProcessor(revisionprocessor.RPDebugLogger()) # Only for debugging

# Iterate through all daily dumps, newest first:
df = datafetcher.DataFetcher()
df.processRecentDumps(dp)

### For testing: just do one fixed daily (needs to be downloaded first if not recent)
#file = df.getDailyFile("20130531")
#dp.processFile(file)
#file.close()

## Store detailed results in files in the results directory:
os.chdir(os.path.dirname(os.path.realpath(__file__))) # change back into our base directory if needed
if not os.path.exists('results') :
	os.makedirs('results')

curdate = df.getLatestDate()
output.write(u'# ' + curdate + "\n")
edits = open('results/edits-' + curdate + '.csv', 'w')
rpedcount.writeResults(edits)
edits.close()
useredits = open('results/editsByUser-' + curdate + '.csv', 'w')
rpedcount.writeEditsByUser(useredits)
useredits.close()

output.close()


