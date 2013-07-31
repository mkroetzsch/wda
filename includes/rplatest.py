#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import revisionprocessor

# Find the latest version of a page process its contents
# using registered EntityProcessor objects.
class RPLatest(revisionprocessor.RevisionProcessor):

	def __init__(self,helper):
		self.helper = helper
		self.curMaxRev = -1
		self.curMaxTimestamp = False
		self.curMaxRawContent = False
		self.curRevsFound = 0
		self.eps = []

	def registerEntityProcessor(self,ep):
		self.eps.append(ep)

	def startPageBlock(self,title,isItem,isNew):
		revisionprocessor.RevisionProcessor.startPageBlock(self,title,isItem,isNew)
		self.curMaxRev = -1
		self.curMaxTimestamp = False
		self.curMaxRawContent = False

	def processRevision(self,revId,timestamp,user,isIp,rawContent):
		if self.isNew and self.curMaxRev < int(revId):
			self.curMaxRev = int(revId)
			self.curMaxTimestamp = timestamp
			self.curMaxRawContent = rawContent

	def endPageBlock(self):
		if self.curMaxRev >= 0:
			self.curRevsFound += 1
			data = self.helper.getVal(self.curMaxRev,self.curMaxRawContent)

			for ep in self.eps:
				ep.processEntity(self.curTitle,int(self.curMaxRev),self.isItem,data)

		revisionprocessor.RevisionProcessor.endPageBlock(self)

	def logReport(self):
		logging.log('     * Number of latest revisions found: ' + str(self.curRevsFound))
		for ep in self.eps:
			ep.logReport()
