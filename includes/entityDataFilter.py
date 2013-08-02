#!/usr/bin/python
# -*- coding: utf-8 -*-

# Class for filtering entities and their content
# based on dynamic settings.
class EntityDataFilter:

	def __init__(self):
		self.includeLanguages = True
		self.includeSites = True
		self.includeStats = True
		self.includePropertyTypes = True
		self.includeRefs = True

	# Create a list of strings that hold information about
	# the current settings, e.g., to be included in comments
	# of created files.
	def getFilterSettingsInfo(self):
		result = []
		if self.includeLanguages == True:
			result.append( 'Languages: *' )
		else:
			result.append( 'Languages: ' + str(self.includeLanguages.keys()) )
		if self.includeSites == True:
			result.append( 'Sites: *' )
		else:
			result.append( 'Sites: ' + str(self.includeSites.keys()) )
		if self.includePropertyTypes == True:
			result.append( 'Property types: *' )
		else:
			result.append( 'Property types: ' + str(self.includePropertyTypes.keys()) )
		result.append( 'Statements: ' + str(self.includeStats) )
		result.append( 'References: ' + str(self.includeRefs) )

		return result

	# Return a hash code that identifies the current settings.
	# This can be used, e.g., in file names.
	def getHashCode(self):
		return '{0:x}'.format(abs(hash(str(self.includeLanguages) + str(self.includeSites) + str(self.includePropertyTypes) + str(self.includeStats) + str(self.includeRefs))))

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

	# Set a property type filter, given as a list of type names
	# (possibly empty), or True to include data of all types.
	def setIncludePropertyTypes(self,propertyTypes):
		if propertyTypes == True:
			self.includePropertyTypes = True
		else:
			self.includePropertyTypes = {}
			for propType in propertyTypes:
				self.includePropertyTypes[propType] = True

	# Set whether statements should be included (bool).
	def setIncludeStatements(self,includeStats):
		self.includeStats = includeStats

	# Set whether references should be included (bool).
	def setIncludeReferences(self,includeRefs):
		self.includeRefs = includeRefs

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

	# Should data for the given property type be included?
	def includePropertyType(self,propType):
		if self.includePropertyTypes == True:
			return True
		else:
			return propType in self.includePropertyTypes

	# Should statements be included?
	def includeStatements(self):
		return self.includeStats

	# Should references be included?
	def includeReferences(self):
		return self.includeRefs