#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging, time, bitarray

# Class to iterate through a MediaWiki dump to process
# all of its revisions. The main entry point is processFile().
# By default, almost nothing is done with the revisions that are found.
# Revision processors can be registered to do something; the method
# registerProcessor() is used for this.
#
# The dump processor will only process revisions of Wikidata Items
# and Properties. Revisions of other pages are ignored and skipped.
class DumpProcessor:

	def __init__(self):
		self.processors = []
		self.processeditems = bitarray.bitarray(2**26) # about 30 M items
		self.processeditems.setall(0)
		self.processedrevisions = bitarray.bitarray(2**28) # about 250 M revisions
		self.processedrevisions.setall(0)
		self.processedproperties = bitarray.bitarray(2**10) # about 1 K properties
		self.processedproperties.setall(0)
		self.linecount = 0
		self.pagecount = 0
		self.revcount = 0
		self.duprevcount = 0
		self.previousTime = 0
		self.startTime = 0

	# Add a new revision processor object that will be called during processing.
	# The object must implement the methods defined for revisionprocessor.RevisionProcessor.
	def registerProcessor(self,processor):
		self.processors.append(processor)

	# Private method that distributes start page block events to processors.
	def startPageBlock(self,title,isItem,isNewEntity):
		for processor in self.processors:
			processor.startPageBlock(title,isItem,isNewEntity)

	# Private method that distributes revision events to processors.
	def processRevision(self,revId,timestamp,user,isIp,rawContent):
		for processor in self.processors:
			processor.processRevision(revId,timestamp,user,isIp,rawContent)

	# Private method that distributes end page block events to processors.
	def endPageBlock(self):
		for processor in self.processors:
			processor.endPageBlock()

	# Private method to log current progress. The dump processor only logs overall time.
	# For more detailed logs, registered revision processors are called.
	def logReport(self):
		timeNeeded = self.previousTime
		if self.startTime != 0:
			timeNeeded += time.time() - self.startTime

		logging.log(' ... processed ' + str(self.linecount) + \
				' lines (' + str(self.pagecount) + ' pages, ' + \
				str(self.revcount) + ' revisions with ' + \
				str(self.duprevcount) + ' dups) in ' + \
				str(round(timeNeeded,2)) + ' seconds.')
		for processor in self.processors:
			processor.logReport()

	# Process the given MediaWiki dump file.
	def processFile(self,file):
		self.startTime = time.time()
		skipToNextPage = True
		isIp = False
		for line in file :
			self.linecount += 1
			if self.linecount % 1000000 == 0:
				self.logReport()
				#break ## break for testing

			# Start of new page:
			if line == '  <page>\n':
				self.pagecount += 1
				title = ''
				isItem = False
				isProperty = False
				isNewEntity = True
				skipToNextPage = False
				prevtimedate = ''
				revid = 0
				timestamp = ''
				timedate = ''
				username = ''
				content = ''
			# Skip further checks if this page is irrelevant
			elif skipToNextPage:
				continue
			# Start of new revision:
			elif line == '    <revision>\n':
				revid = 0
				timestamp = ''
				timedate = ''
				username = ''
				content = ''
			# Finished current revision
			elif line == '    </revision>\n':
				self.revcount += 1
				if self.processedrevisions[int(revid)]:
					#logging.log("Note: encountered duplicate revision " + revid + " of entity " + title + ".")
					self.duprevcount += 1
					continue
				#if prevtimedate == timedate: continue # analyse only one rev per day
				prevtimedate = timedate
				content = content.replace('&quot;', '"')
				if content == '': continue
				self.processRevision(revid,timestamp,username,isIp,content)
				self.processedrevisions[int(revid)] = True
			# Revision ID (ids of pages have fewer spaces)
			elif line.startswith('      <id>'):
				revid = line[10:-6]
			# Revision timestamp
			elif line.startswith('      <timestamp>'):
				timestamp = line[17:-13]
				timedate = timestamp[0:-10]
			# Named user (possibly a bot)
			elif line.startswith('        <username>'):
				username = line[18:-12]
				isIp = False
			# Anonymous user (IP)
			elif line.startswith('        <ip>'):
				username = line[12:-6]
				isIp = True
			# Revision contents
			elif line.startswith('      <text xml:space="preserve">'):
				if isItem or isProperty:
					if not line.endswith('</text>\n'):
						logging.log(line)
					else:
						content = line[33:-8]
			# Title of current page
			elif line.startswith('    <title>'):
				title = line[11:-9]
				isItem = title.startswith('Q') and not title.startswith('Qu')
				if isItem:
					title = line[11:-9]
					isProperty = False
					if not self.processeditems[int(title[1:])]:
						isNewEntity = True
						self.processeditems[int(title[1:])] = True
					else:
						isNewEntity = False
				elif title.startswith('Property:P'):
					isProperty = True
					title = title[9:]
					if not self.processedproperties[int(title[1:])]:
						isNewEntity = True
						self.processedproperties[int(title[1:])] = True
					else:
						isNewEntity = False

				skipToNextPage = not (isItem or isProperty)
				if (isItem or isProperty):
					self.startPageBlock(title,isItem,isNewEntity)
				else:
					skipToNextPage = True
			elif line == '  </page>\n':
				self.endPageBlock()

		self.previousTime += time.time() - self.startTime
		self.startTime = 0
		self.logReport()
