#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import revisionprocessor

# Find the latest version of a page and store its content
# in the database. A more space-efficient encoding is used,
# but the structure of the stored is mostly preserved.
# Some language information is truncated to safe space. This
# is currently hardcoded to keep only English labels, but could
# be configurable.
# Page content is split into several fields in the DB table.
class RPLatest(revisionprocessor.RevisionProcessor):
	def __init__(self,helper,database):
		self.helper = helper
		self.db = database
		self.curMaxRev = -1
		self.curMaxTimestamp = False
		self.curMaxRawContent = False
		self.curRevsFound = 0

		self.descSize = 0
		self.claimSize = 0
		self.labelSize = 0
		self.aliasSize = 0
		self.linkSize = 0

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
			val = self.helper.getVal(self.curMaxRev,self.curMaxRawContent)
			id = int(self.curTitle[1:])

			newdesc_str = str(self.__reduceDictionary(val['description'],('en')))
			newlabel_str = str(self.__reduceDictionary(val['label'],('en')))
			newaliases_str = str(self.__reduceDictionary(val['aliases'],('en')))
			newclaims_str = str(self.__reduceClaims(val['claims']))

			self.descSize += len(newdesc_str)
			self.claimSize += len(newclaims_str)
			self.labelSize += len(newlabel_str)
			self.aliasSize += len(newaliases_str)

			if self.isItem:
				links_str = str(val['links'])
				self.linkSize += len(links_str)
				self.db.updateItemData(id,int(self.curMaxRev),newclaims_str,links_str,newlabel_str,newaliases_str,newdesc_str)
			else:
				self.db.updatePropertyData(id,int(self.curMaxRev),newclaims_str,val['datatype'],newlabel_str,newaliases_str,newdesc_str)

		revisionprocessor.RevisionProcessor.endPageBlock(self)

	# Truncate values of some keys in a dictionary to save space
	def __reduceDictionary(self,data,preserveKeys):
		newdata = {}
		for key in data:
			if key in preserveKeys:
				newdata[key] = data[key]
			else:
				newdata[key] = 1
		return newdata

	# Simplify claim structure to save space
	def __reduceClaims(self,claims):
		newclaims = []
		for claim in claims:
			newclaim = claim.copy()

			newclaim.pop('g',None)

			newclaim['m'] = self.__reduceSnak(newclaim['m'])

			if newclaim['rank'] == 1:
				newclaim.pop('rank',None)

			newqualifiers = []
			hasQ = False
			for snak in newclaim['q']:
				hasQ = True
				newqualifiers.append(self.__reduceSnak(snak))
			if hasQ:
				newclaim['q'] = newqualifiers
			else:
				newclaim.pop('q',None)

			newrefs = []
			hasRef = False
			for ref in newclaim['refs']:
				hasRef = True
				newref = []
				for snak in ref:
					newref.append(self.__reduceSnak(snak))
				newrefs.append(newref)
			if hasRef:
				newclaim['refs'] = newrefs
			else:
				newclaim.pop('refs',None)

			newclaims.append(newclaim)
		return newclaims

	def __reduceSnak(self,snak):
		if snak[0] == 'value':
			if snak[2] == 'wikibase-entityid':
				if snak[3]['entity-type'] == 'item':
					return ('R',snak[1],snak[3]['numeric-id'])
			if snak[2] == 'string':
				return ('S',snak[1],snak[3])
			if snak[2] == 'time':
				return ('T',snak[1],snak[3]['precision'],snak[3]['time'],snak[3]['timezone'],snak[3]['calendarmodel'][35:],snak[3]['after'],snak[3]['before'])

		# Fallback:
		return tuple(snak)

	def logReport(self):
		logging.log('     * Number of latest revisions found: ' + str(self.curRevsFound))
		logging.log('     * Size used for latest revs (in chars): claims: ' + str(self.claimSize) + ', aliases: ' + str(self.aliasSize) + ', labels: ' + str(self.labelSize) + ', links: ' + str(self.linkSize) + ', descs: ' + str(self.descSize))
