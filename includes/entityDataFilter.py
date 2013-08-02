#!/usr/bin/python
# -*- coding: utf-8 -*-

# Class for filtering entities and their content
# based on dynamic settings.
class EntityDataFilter:

	def __init__(self):
		self.includeLanguages = True
		self.includeSites = True
		self.includeStats = True

	# Set a language filter, given as a list of
	# language codes (possibly empty), or True
	# to allow all languages.
	def setIncludeLanguages(self,languageCodes):
		if languageCodes == True:
			self.includeLanguages = True
		else:
			self.includeLanguages = {}
			for langCode in languageCodes:
				self.includeLanguages[langCode] = True

	# Set a site filter, given as a list of site ids
	# (possibly empty), or True to include all sites.
	def setIncludeSites(self,siteIds):
		if siteIds == True:
			self.includeSites = True
		else:
			self.includeSites = {}
			for siteId in siteIds:
				self.includeSites[siteId] = True

	# Set whether statements should be included in export (bool).
	def setIncludeStatements(self,includeStats):
		self.includeStats = includeStats

	# Should the given language be included?
	def includeLanguage(self,langCode):
		if self.includeLanguages == True:
			return True
		else:
			return langCode in self.includeLanguages

	# Should the given site be included?
	def includeSite(self,siteId):
		if self.includeSites == True:
			return True
		else:
			return siteId in self.includeSites

	# Should statements be included?
	def includeStatements(self):
		return self.includeStats