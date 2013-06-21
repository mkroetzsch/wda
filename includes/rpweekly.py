#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import revisionprocessor

# Store statistic information in the database for
# the most recent revision in a given interval (14 days
# by default). This information can later be analysed
# to create historic reports. Only simplified/aggregate
# data is stored to avoid very large data sets.
class RPWeekly(revisionprocessor.RevisionProcessor):
	interval = 14

	def __init__(self,helper,database):
		self.helper = helper
		self.db = database
		self.curWeek = -1
		self.maxDay = -1

		self.recordedItemRevs = 0
		self.recordedPropertyRevs = 0

	def startPageBlock(self,title,isItem,isNew):
		revisionprocessor.RevisionProcessor.startPageBlock(self,title,isItem,isNew)
		self.curMaxRev = -1
		self.curWeek = -1
		self.maxDay = -1
		self.curMaxRawContent = False

	def processRevision(self,revId,timestamp,user,isIp,rawContent):
		week = self.helper.getDateInfo(timestamp)[3] / RPWeekly.interval
		#print "Week: " + str(week)  + " -- " + timestamp + " R" + revId

		if self.curWeek == -1:
			self.curWeek = week
			self.maxDay = (week+1)*RPWeekly.interval-1
		elif week != self.curWeek:
			self.flushData()
			self.curWeek = week
			self.maxDay = (week+1)*RPWeekly.interval-1

		if self.curMaxRev < int(revId):
			self.curMaxRev = int(revId)
			self.curMaxRawContent = rawContent

	def endPageBlock(self):
		self.flushData()
		revisionprocessor.RevisionProcessor.endPageBlock(self)

	def flushData(self):
		if self.curMaxRev == -1:
			return

		if self.isItem:
			self.flushItemData()
		else:
			self.flushPropertyData()

		self.curMaxRev = -1
		self.curMaxRawContent = False

	def flushItemData(self):
		id = int(self.curTitle[1:])
		dbRev = self.db.getItemRevStatRevision(id,self.maxDay)
		if dbRev <= self.curMaxRev:
			#if dbRev != -1:
				#print "Found existing dbRev: " + str(dbRev) + " for item " + self.curTitle + ' r' + str(self.curMaxRev)
			self.recordedItemRevs += 1

			#print "Writing data for " + self.curTitle + ' r' + str(self.curMaxRev) + ' day ' + str(self.maxDay) + ' dbRev: ' + str(dbRev)

			val = self.helper.getVal(self.curTitle,self.curMaxRawContent)

			#print "Content: "+ self.curMaxRawContent

			propsM = {}
			propsQ = {}
			propsR = {}
			statRefNum = 0
			statQNum = 0
			for claim in val['claims']:
				self.__countSnakProperty(claim['m'],propsM)
				if claim['q']:
					statQNum += 1
					for qsnak in claim['q']:
						self.__countSnakProperty(qsnak,propsQ)

				if claim['refs']:
					statRefNum += 1
					for refList in claim['refs']:
						for rsnak in refList:
							self.__countSnakProperty(rsnak,propsR)

			labelLangs = val['label'].keys()
			descLangs = val['description'].keys()
			aliasLangs = {}
			aliasNum = 0
			for langKey in val['aliases']:
				aliasLangs[langKey] = len(val['aliases'][langKey])
				aliasNum += aliasLangs[langKey]

			self.db.updateItemRevStatsData(id,self.curMaxRev,self.maxDay,str((labelLangs,descLangs,aliasLangs)),str((propsM,propsQ,propsR)), len(val['claims']), statRefNum, statQNum, len(val['label']), len(val['description']), len(val['links']), aliasNum)
		else:
			pass
			#print "Not writing data for item " + self.curTitle + ' r' + str(self.curMaxRev)

	def flushPropertyData(self):
		id = int(self.curTitle[1:])
		dbRev = self.db.getPropertyRevStatRevision(id,self.maxDay)
		if dbRev <= self.curMaxRev:
			self.recordedItemRevs += 1
			#print "Writing data for " + self.curTitle + ' r' + str(self.curMaxRev)
			val = self.helper.getVal(self.curTitle,self.curMaxRawContent)

			labelLangs = val['label'].keys()
			descLangs = val['description'].keys()
			aliasLangs = {}
			aliasNum = 0
			for langKey in val['aliases']:
				aliasLangs[langKey] = len(val['aliases'][langKey])
				aliasNum += aliasLangs[langKey]
			self.db.updatePropertyRevStatsData(id,self.curMaxRev,self.maxDay,str((labelLangs,descLangs,aliasLangs)),len(val['label']), len(val['description']),aliasNum)
		else:
			pass
			#print "Not writing data for prop " + self.curTitle + ' r' + str(self.curMaxRev)

	def logReport(self):
		logging.log('     * Recorded statistics for ' + str(self.recordedItemRevs) + ' item revisions.')


	def __countSnakProperty(self,snak,propCounts):
		if snak[1] not in propCounts:
			propCounts[snak[1]] = 0
		propCounts[snak[1]] += 1
