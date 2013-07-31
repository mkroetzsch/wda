#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import entityprocessor

# Entity processor that writes entity data to a given database.
# A more space-efficient encoding is used for the data,
# but the structure of the stored data is mostly preserved.
# Some language information is truncated to safe space. This
# is currently hardcoded to keep only English labels, but could
# be configurable.
# Page content is split into several fields in the DB table.
class EPDatabase(entityprocessor.EntityProcessor):

	def __init__(self,database):
		self.db = database

		self.descSize = 0
		self.claimSize = 0
		self.labelSize = 0
		self.aliasSize = 0
		self.linkSize = 0

	def processEntity(self,title,revision,isItem,data):
		id = int(title[1:])

		newdesc_str = str(self.__reduceDictionary(data['description'],('en')))
		newlabel_str = str(self.__reduceDictionary(data['label'],('en')))
		newaliases_str = str(self.__reduceDictionary(data['aliases'],('en')))
		newclaims_str = str(self.__reduceClaims(data['claims']))

		self.descSize += len(newdesc_str)
		self.claimSize += len(newclaims_str)
		self.labelSize += len(newlabel_str)
		self.aliasSize += len(newaliases_str)

		if self.isItem:
			links_str = str(data['links'])
			self.linkSize += len(links_str)
			self.db.updateItemData(id,revision,newclaims_str,links_str,newlabel_str,newaliases_str,newdesc_str)
		else:
			self.db.updatePropertyData(id,revision,newclaims_str,data['datatype'],newlabel_str,newaliases_str,newdesc_str)

	def logReport(self):
		logging.log('     * Size used for latest revs (in chars): claims: ' + str(self.claimSize) + ', aliases: ' + str(self.aliasSize) + ', labels: ' + str(self.labelSize) + ', links: ' + str(self.linkSize) + ', descs: ' + str(self.descSize))

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