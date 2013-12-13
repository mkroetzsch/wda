#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import entityprocessor
import urllib
import datetime

# Entity processor that writes entity data to a file using
# a compact syntactic format.
class EPTurtleFile(entityprocessor.EntityProcessor):

	def __init__(self,outputFile,dataFilter):
		self.output = outputFile
		self.dataFilter = dataFilter
		self.propertyTypes = {}
		self.propertyDeclarationQueue = []
		self.filterName = self.dataFilter.getHashCode()
		# Keep some statistics (inserted at end of file):
		self.entityCount = 0
		self.propertyCount = 0 # number of OWL property declarations, not of Wikidata properties
		self.propertyLookupCount = 0 # number of additional online lookups
		self.statStatementCount = 0
		self.statReferenceCount = 0
		self.statStmtPropertyCounts = {}
		self.statStmtTypeCounts = {}
		self.statQualiPropertyCounts = {}
		self.statQualiTypeCounts = {}
		self.statRefPropertyCounts = {}
		self.statRefTypeCounts = {}
		self.statTripleCount = 0

		# Make header:
		self.output.write( '### Wikidata OWL/RDF Turtle dump\n' )
		self.output.write( '# Filter settings (' + self.filterName + ')\n' )
		for infostr in self.dataFilter.getFilterSettingsInfo():
			self.output.write( '# - ' + infostr + '\n' )
		self.output.write( '# Generated on ' + str(datetime.datetime.now()) + '\n###\n\n' )

		self.output.write("@prefix w: <http://www.wikidata.org/entity/> .\n")
		self.output.write("@prefix wo: <http://www.wikidata.org/ontology#> .\n")
		self.output.write("@prefix r: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n")
		self.output.write("@prefix rs: <http://www.w3.org/2000/01/rdf-schema#> .\n")
		self.output.write("@prefix o: <http://www.w3.org/2002/07/owl#> .\n")
		self.output.write("@prefix x: <http://www.w3.org/2001/XMLSchema#> .\n")
		self.output.write("@prefix so: <http://schema.org/> .\n")
		self.output.write("@prefix sk: <http://www.w3.org/2004/02/skos/core#> .\n")
		self.output.write("@prefix pv: <http://www.w3.org/ns/prov#> .\n")
		# Also inline some basic property declarations to help processing without resolving imports:
		# (class declarations are not needed, as they can be inferred from the context in all cases)
		self.__writeTriple( "wo:propertyType", "a", "o:ObjectProperty" )
		self.__writeTriple( "wo:globe", "a", "o:ObjectProperty" )
		self.__writeTriple( "wo:latitude", "a", "o:DatatypeProperty" )
		self.__writeTriple( "wo:longitude", "a", "o:DatatypeProperty" )
		self.__writeTriple( "wo:altitude", "a", "o:DatatypeProperty" )
		self.__writeTriple( "wo:gcPrecision", "a", "o:DatatypeProperty" )
		self.__writeTriple( "wo:time", "a", "o:DatatypeProperty" )
		self.__writeTriple( "wo:timePrecision", "a", "o:DatatypeProperty" )
		#self.__writeTriple( "wo:timePrecisionAfter", "a", "o:DatatypeProperty" ) # currently unused
		#self.__writeTriple( "wo:timePrecisionBefore", "a", "o:DatatypeProperty" ) # currently unused
		self.__writeTriple( "wo:preferredCalendar", "a", "o:ObjectProperty" )
		# Other external properties that have a clear declaration:
		# (we omit the rdfs and skos properties, which lack a clear typing)
		self.__writeTriple( "pv:wasDerivedFrom", "a", "o:ObjectProperty" )
		self.__writeTriple( "so:about", "a", "o:ObjectProperty" )
		self.__writeTriple( "so:inLanguage", "a", "o:DatatypeProperty" )
		self.output.write("\n")

	def processEntity(self,title,revision,isItem,data):
		self.entityCount += 1
		self.refs = {} # collect references to export duplicates only once per item

		if isItem:
			self.__startTriples( 'w:' + title, "a", "wo:Item" )
		else:
			self.__startTriples( 'w:' + title, "a", "wo:Property" )

		# Write datatype information, if any
		if 'datatype' in data:
			if self.dataFilter.includeStatements():
				self.__setPropertyType(title,data['datatype'],True)
			if data['datatype'] == 'wikibase-item':
				self.__addPO( "wo:propertyType", "wo:propertyTypeItem" )
			elif data['datatype'] == 'string':
				self.__addPO( "wo:propertyType", "wo:propertyTypeString" )
			elif data['datatype'] == 'commonsMedia':
				self.__addPO( "wo:propertyType", "wo:propertyTypeCommonsMedia" )
			elif data['datatype'] == 'time':
				self.__addPO( "wo:propertyType", "wo:propertyTypeTime" )
			elif data['datatype'] == 'globe-coordinate':
				self.__addPO( "wo:propertyType", "wo:propertyTypeGlobeCoordinates")
			else:
				logging.log( '*** Warning: Unknown property type "' + data['datatype'] + '".'  )

		# Write labels, descriptions, and aliases:
		self.__writeLanguageLiteralValues('rs:label', data['label'])
		self.__writeLanguageLiteralValues('so:description', data['description'])
		self.__writeLanguageLiteralValues('sk:altLabel', data['aliases'], True)

		# Connect statements to item:
		statements = []
		if self.dataFilter.includeStatements():
			curProperty = ''
			for statement in data['claims']:
				datatype = self.__getStatementDatatype(statement)
				if not self.dataFilter.includePropertyType(datatype):
					continue
				statements.append(statement)
				i = statement['g'].index('$') + 1
				statement['localname'] = title + 'S' + statement['g'][i:]
				if curProperty == statement['m'][1]:
					self.__addO( "w:" + statement['localname'])
				else:
					curProperty = statement['m'][1]
					self.__addPO( "w:P" + str(curProperty) + "s", "w:" + statement['localname'])

		self.__endTriples()

		# Export statements:
		if self.dataFilter.includeStatements():
			for statement in statements:
				self.__writeStatementData(statement)

		# Export collected references:
		if self.dataFilter.includeReferences():
			for key in self.refs.keys():
				self.__startTriples( 'w:' + key, "a", "wo:Reference" )
				for snak in self.refs[key]:
					self.__writeSnakData('r', snak)
				self.__endTriples()

		# Export links:
		for sitekey in data['links'].keys() :
			if not self.dataFilter.includeSite(sitekey):
				continue
			if sitekey == 'commonswiki':
				urlPrefix = 'http://commons.wikimedia.org/wiki/'
			elif sitekey[-10:] == 'wikivoyage':
				urlPrefix = 'http://' + sitekey[:-10].replace('_','-') + '.wikivoyage.org/wiki/'
			elif sitekey[-4:] == 'wiki':
				urlPrefix = 'http://' + sitekey[:-4].replace('_','-') + '.wikipedia.org/wiki/'
			else:
				logging.log("*** Warning: the following sitekey was not understood: " + sitekey)
				continue

			if isinstance(data['links'][sitekey], str): # Old format (name string)
				articletitle = data['links'][sitekey].replace(' ','_').encode('utf-8')
			else: # New format (dict with 'name' (string) and 'badges' (dict))
				articletitle = data['links'][sitekey]['name'].replace(' ','_').encode('utf-8')

			self.__startTriples( "<" + urlPrefix + urllib.quote(articletitle) + ">", "a", "so:Article" )
			self.__addPO( "so:about", "w:" + title )
			if sitekey in siteLanguageCodes:
				self.__addPO( "so:inLanguage", "\"" + siteLanguageCodes[sitekey] + "\"")
			elif sitekey == 'commonswiki': # Commons has no uniform language; do not export
				pass
			else:
				logging.log( '*** Warning: Language code unknown for site "' + sitekey + '".'  )
			self.__endTriples()

		self.__writePropertyDeclarations()

	def logReport(self):
		## Dump collected types to update the cache at the end of this file (normally done only at the very end):
		#self.__knownTypesReport()
		logging.log('     * Turtle serialization (' + self.filterName + '): serialized ' + str(self.statTripleCount) + ' triples, looked up ' + str(self.propertyLookupCount) + ' property types online ...')
		logging.log('     * ... ' + str(self.entityCount) + ' entities, ' + str(self.propertyCount) + ' additional OWL property declarations, ' + str(self.statStatementCount) + ' statements, ' + str(self.statReferenceCount) + ' references ...')
		if self.dataFilter.includeStatements():
			logging.log('     * ... statement types: ' + str(self.statStmtTypeCounts))
			logging.log('     * ... qualifier types: ' + str(self.statQualiTypeCounts))
			logging.log('     * ... reference types: ' + str(self.statRefTypeCounts) + ' (counting each reference only once per item)')
		## Debug:
		#self.close()
		#exit()

	# Create a report about known property types if any had
	# to be looked up online.
	def __knownTypesReport(self):
		if self.propertyLookupCount > 0:
			logging.log('     * Turtle serialization note: some property types needed to be looked up online.')
			logging.log('     * You can avoid this by updating the data for "knownPropertyTypes" at the bottom')
			logging.log('     * of the file includes/epTurtleFileWriter.py with the following contents:\n')
			logging.logMore('knownPropertyTypes = {')
			count = 0
			for key in sorted(self.propertyTypes.keys()):
				if count > 0:
					logging.logMore(", ")
				if count % 4 == 0:
					logging.logMore("\n\t")
				logging.logMore( "'" + key + "' : '" + self.propertyTypes[key] + "'" )
				count += 1
			logging.log( '\n}' )
			logging.log('\n\n\n')

	def __addStatisticsComments(self):
		self.output.write('\n\n### Turtle seliarlization completed:\n# * ' +
			str(self.statTripleCount) + ' triples\n# * ' +
			str(self.entityCount) + ' entities\n# * ' +
			str(self.propertyCount) + ' additional OWL property declarations\n# * ' +
			str(self.statStatementCount) + ' statements\n# * ' +
			str(self.statReferenceCount) + ' references\n# * types of main properties: ' +
			str(self.statStmtTypeCounts) + '\n# * types of qualifier properties: ' +
			str(self.statQualiTypeCounts) + '\n# * types of reference properties: ' +
			str(self.statRefTypeCounts) + '\n')

		if self.dataFilter.includeStatements():
			self.output.write('###\n### The following is a CSV compatible list with property statistics:\n' +
				'### (Values for references refer to how often a value for a certain Wikidata\n' +
				'### property was included in the RDF export. It may occur more often if\n' +
				'### several statements of an item use the same reference -- a common case.)\n###\n' +
				'#,property id,type,use as main property,use in qualifiers,use in references\n')
			for p in sorted(self.statStmtPropertyCounts, key=self.statStmtPropertyCounts.get, reverse=True):
				self.output.write( '#,' + str(p) + ',' + self.__getPropertyType('P' + str(p)) + ',' + str(self.statStmtPropertyCounts[p]) )
				if p in self.statQualiPropertyCounts:
					self.output.write( ',' + str(self.statQualiPropertyCounts[p]) )
				else:
					self.output.write( ',0' )
				if p in self.statRefPropertyCounts:
					self.output.write( ',' + str(self.statRefPropertyCounts[p]) )
				else:
					self.output.write( ',0' )
				self.output.write( '\n' )
			self.output.write('###END###\n')

		self.output.write('###\n')

	def close(self):
		self.__addStatisticsComments()
		self.output.write("\n\n### Export completed successfully. The End. ###")
		self.__knownTypesReport()
		self.output.close()

	# Find type information about a property.
	def __getPropertyType(self,propertyTitle):
		if propertyTitle not in self.propertyTypes:
			self.propertyTypes[propertyTitle] = self.__fetchPropertyType(propertyTitle)
		return self.propertyTypes[propertyTitle]

	# Fetch current property type.
	# Get the current type of a property from the Web.
	def __fetchPropertyType(self,propertyTitle):
		# Use local cache if possible (property types never change)
		if propertyTitle in knownPropertyTypes:
			return knownPropertyTypes[propertyTitle]

		logging.logMore('Fetching current datatype of property ' + propertyTitle + ' from wikidata.org ... ' )
		self.propertyLookupCount += 1
		for line in urllib.urlopen('http://www.wikidata.org/w/api.php?action=wbgetentities&ids=' + propertyTitle + '&props=datatype&format=json'):
			data = eval(line)
			if 'entities' in data and propertyTitle in data['entities'] and 'datatype' in data['entities'][propertyTitle]:
				logging.log('found type ' + data['entities'][propertyTitle]['datatype'])
				knownPropertyTypes[propertyTitle] = data['entities'][propertyTitle]['datatype'] # share with all instances of this class
				return data['entities'][propertyTitle]['datatype']

		logging.log('error')
		logging.log('*** Could not find the datatype for property ' + propertyTitle + ' online. Export might be erroneous.')
		return None

	# Find the value range for a property based on its type
	def __getPropertyRange(self,propertyTitle):
		return owlPropertyRanges[self.__getPropertyType(propertyTitle)]

	# Record type information about a property.
	# If definite is False, then the given type is assumed to be based on
	# some datavalue that was found for the property. In some cases, one
	# cannot tell the type from the datavalue (currently only for strings).
	# If this happens, the method will look up the exact type, to be sure.
	# The definite type is returned by the function.
	def __setPropertyType(self,propertyTitle,propertyType,definite=False):
		if propertyTitle not in self.propertyTypes:
			# String literals could also belong to commonsMedia; check
			if not definite and propertyType == 'string':
				propertyType = self.__fetchPropertyType(propertyTitle)
			self.propertyTypes[propertyTitle] = propertyType
			self.propertyDeclarationQueue.append(propertyTitle)
		return self.propertyTypes[propertyTitle]

	def __writePropertyDeclarations(self):
		for propertyTitle in self.propertyDeclarationQueue:
			self.__writeTriple( 'w:' + propertyTitle + "s", "a", "o:ObjectProperty" )
			if self.__getPropertyRange(propertyTitle) == 'o:Thing':
				self.__writeTriple( 'w:' + propertyTitle + "v", "a", "o:ObjectProperty" )
				self.__writeTriple( 'w:' + propertyTitle + "r", "a", "o:ObjectProperty" )
				self.__writeTriple( 'w:' + propertyTitle + "q", "a", "o:ObjectProperty" )
			else:
				self.__writeTriple( 'w:' + propertyTitle + "v", "a", "o:DatatypeProperty" )
				self.__writeTriple( 'w:' + propertyTitle + "r", "a", "o:DatatypeProperty" )
				self.__writeTriple( 'w:' + propertyTitle + "q", "a", "o:DatatypeProperty" )
			self.output.write( '\n' )
			self.propertyCount += 4

		self.propertyDeclarationQueue = []

	# Encode string literals for use in Turtle. It is assumed that
	# the given language code is supported, so this must be checked first.
	# The string is expected to be JSON escaped (as in Wikidata exports).
	def __encodeStringLiteral(self,string,lang = False):
		literal = string.replace("\\","\\\\").replace('"','\\"').encode('utf-8')
		# Note: Turtle also supports the escape \', but using it does not seem necessary.
		if lang == False:
			return '"' + literal + '"'
		else:
			return '"' + literal + '"@' + langCodes[lang]

	# Encode float literals for use in Turtle.
	def __encodeFloatLiteral(self,number):
		return '"' + str(number) + '"^^x:float'

	# Encode integer literals for use in Turtle.
	def __encodeIntegerLiteral(self,number):
		try:
			return '"' + str(int(number)) + '"^^x:int'
		except ValueError: # let's be prepared for non-numerical strings here
			logging.log("*** Warning: unexpected number format '" + str(number) + "'.")
			return '"+42"^^x:int' # valid but not canonical = easy to find in file

	# Encode time literals for use in Turtle.
	# The XSD type that is chosen depends on the literal's precision.
	def __encodeTimeLiteral(self,wikidataTime,precision):
		# The meaning of precision is:
		# 11: day, 10: month, 9: year, 8: decade, ..., 0: 10^9 years

		yearLength = 0
		try:
			yearnum = int(wikidataTime[:12])
			month = wikidataTime[13:15]
			day = wikidataTime[16:18]
		except ValueError: # some rare values have different length for the year string; try again
			yearLength = wikidataTime.find('-',1)

		if yearLength > 0:
			try:
				yearnum = int(wikidataTime[:yearLength])
				month = wikidataTime[yearLength+1:yearLength+3]
				day = wikidataTime[yearLength+4:yearLength+6]
			except ValueError: # some rare values have broken formats
				logging.log("*** Warning: unexpected date format '" + wikidataTime + "'." + str(yearLength))
				#return '"' + wikidataTime + '"^^x:dateTime' # < not valid in some old dumps
				return '"2007-05-12T10:30:42Z"^^x:dateTime' # use an arbitrary but valid time; should be very rare (only in old dumps)

		# Wikidata encodes the year 1BCE as 0000, while XML Schema, even in
		# version 2, does not allow 0000 and interprets -0001 as 1BCE. Thus
		# all negative years must be shifted by 1, but we only do this if
		# the year is precise.
		if yearnum == 0 or ( yearnum < 0 and precision >= 9 ):
			yearnum = -1
		if yearnum >= 0: # of course, yearnum == 0 is imposible here
			year = '{0:04d}'.format(yearnum)
		else: # Python padding counts the "-" sign and reduces 0s by one
			year = '{0:05d}'.format(yearnum)

		if precision == 11:
			return '"' + year + '-' + month + '-' + day + '"^^x:date'
		elif precision == 10:
			return '"' + year + '-' + month + '"^^x:gYearMonth'
		elif precision <= 9:
			return '"' + year + '"^^x:gYear'
		else:
			logging.log("*** Warning: unexpected precision " + str(precision) + " for date " + wikidataTime + '.')
			return '"' + wikidataTime + '"^^x:dateTime'

	# Write a list of language literal values for a given property.
	def __writeLanguageLiteralValues(self,prop,literals,valueList=False):
		first = True
		for lang in literals.keys():
			if lang not in langCodes or not self.dataFilter.includeLanguage(lang):
				continue
			#if valueList and literals[lang] == []: # deal with https://bugzilla.wikimedia.org/show_bug.cgi?id=44717
				#continue

			if valueList:
				for literal in literals[lang]:
					if first:
						first = False
						self.__addPO(prop, self.__encodeStringLiteral(literal, lang))
					else:
						self.__addO( self.__encodeStringLiteral(literal, lang) )
			else:
				if first:
					first = False
					self.__addPO(prop, self.__encodeStringLiteral(literals[lang], lang))
				else:
					self.__addO( self.__encodeStringLiteral(literals[lang], lang) )

	# Find the datatype of the main snak of a statement.
	def __getStatementDatatype(self,statement):
		# While we are at it, we also remember the type of the property.
		snak = statement['m']
		mainProperty = 'P' + str(snak[1])
		if snak[0] == 'value' :
			if snak[2] in datatypesByValueTypes:
				mainType = self.__setPropertyType(mainProperty, datatypesByValueTypes[snak[2]])
			else :
				mainType = None
		else:
			mainType = self.__getPropertyType(mainProperty)

		return mainType

	# Write the data for one statement.
	def __writeStatementData(self,statement):
		self.statStatementCount += 1
		self.valuesGC = {} # collect coordinates values and export them after each statement
		self.valuesTI = {} # collect time values and export them after each statement

		self.__startTriples( 'w:' + statement['localname'], "a", "wo:Statement" )
		self.__writeSnakData('v', statement['m'])
		for q in statement['q']:
			self.__writeSnakData('q', q)

		if self.dataFilter.includeReferences():
			for ref in statement['refs']:
				key = "R" + self.__getHashForLocalName(ref)
				self.refs[key] = ref
				self.__addPO( "pv:wasDerivedFrom", "w:" + key )
				self.statReferenceCount += 1

		self.__endTriples()

		# Export times
		for key in self.valuesTI.keys():
			self.__writeTimeValue(key,self.valuesTI[key])

		# Export coordinates
		for key in self.valuesGC.keys():
			self.__writeCoordinatesValue(key,self.valuesGC[key])


	# Write the data for a time datavalue with the given local name.
	def __writeTimeValue(self,localname,value):
		# TODO Timezone not exported yet. The timezone support should
		# be similar to calendar model support (all dates are UTC, but
		# there can be a "preferred timezone for display")
		self.__startTriples( 'w:' + localname, "a", "wo:TimeValue" )
		self.__addPO( "wo:time", self.__encodeTimeLiteral(value['time'],value['precision']) )
		self.__addPO( "wo:timePrecision", self.__encodeIntegerLiteral(value['precision']) )
		## TODO Currently unused -- do not export yet.
		#self.__addPO( "wo:timePrecisionBefore", self.__encodeIntegerLiteral(value['before']) )
		#self.__addPO( " wo:timePrecisionAfter", self.__encodeIntegerLiteral(value['after']) )
		self.__addPO( "wo:preferredCalendar", "w:" + value['calendarmodel'][31:] )
		self.__endTriples()

	# Write the data for a coordinates datavalue with the given local name.
	def __writeCoordinatesValue(self,localname,value):
		self.__startTriples( 'w:' + localname, "a", "wo:GlobeCoordinatesValue" )
		self.__addPO( "wo:latitude", self.__encodeFloatLiteral(value['latitude']) )
		self.__addPO( "wo:longitude", self.__encodeFloatLiteral(value['longitude']) )
		if value['altitude'] != None:
			self.__addPO( "wo:altitude", self.__encodeFloatLiteral(value['altitude']) )
		if value['precision'] != None:
			self.__addPO( "wo:gcPrecision", self.__encodeFloatLiteral(value['precision']) )
		if value['globe'] != None:
			try:
				globeId = str(int(value['globe'][32:]))
				self.__addPO( "wo:globe", "w:Q" + globeId )
			except ValueError:
				logging.log("*** Warning: illegal globe specification '" + value['globe'] + "'.")
		self.__endTriples()

	# Write the data for one snak. Since we use different variants of
	# property URIs depending on context, the context is also given;
	# it should be one of 'v' (main value), 'q' (qualifier), and 'r'
	# (reference).
	def __writeSnakData(self,snakContext,snak):
		includeSnak = True
		wbProperty = 'P' + str(snak[1]) # Not to be confused with prop
		prop = "w:" + wbProperty + snakContext
		datatype = None
		if snak[0] == 'value' :
			if snak[2] in datatypesByValueTypes:
				datatype = self.__setPropertyType(wbProperty, datatypesByValueTypes[snak[2]])

			if self.dataFilter.includePropertyType(datatype):
				if datatype == 'wikibase-item':
					self.__addPO( prop, "w:Q" + str(snak[3]['numeric-id']) )
				elif datatype == 'commonsMedia':
					self.__addPO( prop, "<http://commons.wikimedia.org/wiki/File:" +  urllib.quote(snak[3].replace(' ','_').encode('utf-8')) + '>' )
				elif datatype == 'string':
					self.__addPO( prop, self.__encodeStringLiteral(snak[3]) )
				elif datatype == 'url':
					self.__addPO( prop, '<' +  urllib.quote(snak[3].encode('utf-8')) + '>' )
				elif datatype == 'time' :
					key = 'VT' + self.__getHashForLocalName(snak[3])
					self.valuesTI[key] = snak[3]
					self.__addPO( prop, "w:" + key )
				elif datatype == 'globe-coordinate' :
					key = 'VC' + self.__getHashForLocalName(snak[3])
					self.valuesGC[key] = snak[3]
					self.__addPO( prop, "w:" + key )
				elif datatype == None :
					logging.log('*** Warning: Could not find type for snak "' + str(snak) + '". Export will be incomplete.\n')
					includeSnak = False
				else :
					logging.log('*** Warning: Unsupported value snak of type "' + str(datatype) + '":\n' + str(snak) + '\nExport might be incomplete.\n')
					includeSnak = False
			else:
				includeSnak = False
		elif snak[0] == 'somevalue' :
			datatype = self.__getPropertyType(wbProperty)
			if self.dataFilter.includePropertyType(datatype):
				propRange = self.__getPropertyRange(wbProperty)
				self.__addPO( "a", "[ a o:Restriction; o:onProperty " + prop + "; o:someValuesFrom " + propRange + " ]" )
				self.statTripleCount += 3
			else:
				includeSnak = False
		elif snak[0] == 'novalue' :
			datatype = self.__getPropertyType(wbProperty)
			if self.dataFilter.includePropertyType(datatype):
				propRange = self.__getPropertyRange(wbProperty)
				if propRange == 'o:Thing':
					self.__addPO( "a", "[ a o:Class; o:complementOf [ a o:Restriction; o:onProperty " + prop + "; o:someValuesFrom o:Thing ] ]" )
					#self.__addPO( "a", "[ a o:Restriction; o:onProperty " + prop + "; o:allValuesFrom o:Nothing ]" ) # < shorter, but less uniform compared to data case
					self.statTripleCount += 5
				else:
					self.__addPO( "a", "[ a o:Class; o:complementOf [ a o:Restriction; o:onProperty " + prop + "; o:someValuesFrom rs:Literal ] ]" )
					self.statTripleCount += 5
			else:
				includeSnak = False
		else :
			logging.log('*** Warning: Unsupported snak:\n' + str(snak) + '\nExport might be incomplete.\n')
			includeSnak = False

		if not includeSnak:
			self.__addPO( "a", "wo:IncompletelyExported" )
		else:
			if snakContext == 'v':
				statPropertyCounts = self.statStmtPropertyCounts
				statTypeCounts = self.statStmtTypeCounts
			elif snakContext == 'q':
				statPropertyCounts = self.statQualiPropertyCounts
				statTypeCounts = self.statQualiTypeCounts
			else: #  snakContext == 'r'
				statPropertyCounts = self.statRefPropertyCounts
				statTypeCounts = self.statRefTypeCounts

			if snak[1] in statPropertyCounts:
				statPropertyCounts[snak[1]] += 1
			else:
				statPropertyCounts[snak[1]] = 1
			if datatype != None and datatype in statTypeCounts:
				statTypeCounts[datatype] += 1
			else:
				statTypeCounts[datatype] = 1
			# Also make sure that all properties occur in the statement statistics for later printout:
			if not snak[1] in self.statStmtPropertyCounts:
				self.statStmtPropertyCounts[snak[1]] = 0

	def __getHashForLocalName(self, obj):
		return '{0:x}'.format(abs(hash(str(obj))))

	# Write a single, complete triple on one line
	def __writeTriple(self,s,p,o):
		self.output.write( "\n" + s + "\t" + p + "\t" + o + " ." )
		self.statTripleCount += 1

	# Start a new block of triples. It needs to be closed with
	# __endTriples().
	def __startTriples(self,s,p,o):
		self.output.write( "\n" + s + "\n\t" + p + "\t" + o )

	# Add another p-o to a previously started triple block.
	def __addPO(self,p,o):
		self.output.write( " ;\n\t" + p + "\t" + o )
		self.statTripleCount += 1

	# Add another o to a previously started triple block.
	def __addO(self,o):
		self.output.write( "," + o)
		self.statTripleCount += 1

	# Close a previously started triple block.
	def __endTriples(self):
		self.output.write(" .\n")

# Wikidata datatypes for which the OWL value property
# is an ObjectProperty (rather than a DatatypeProperty).
owlPropertyRanges = {
	'wikibase-item': 'o:Thing',
	'string': 'x:string',
	'time': 'o:Thing',
	'url': 'o:Thing',
	'globe-coordinate': 'o:Thing',
	'commonsMedia': 'o:Thing',
	None : 'o:Thing' # fallback (happens if missing property type cannot be fetched online)
}

# The property types of Wikibase do not corresond to the
# kinds of datavalues it encodes (though sometimes, confusingly,
# the same string names are used). This dictionary assigns the
# default property type to each known value type.
datatypesByValueTypes = {
	'wikibase-entityid': 'wikibase-item',
	'string': 'string',
	'time': 'time',
	'globecoordinate': 'globe-coordinate'
}

# The meaning of Wikimedia language codes in terms of
# BCP 47 http://www.rfc-editor.org/rfc/bcp/bcp47.txt.
# All official IANA codes are at
# http://www.iana.org/assignments/language-subtag-registry/language-subtag-registry
# Exceptional Wikipedia language codes are at
# http://meta.wikimedia.org/wiki/Special_language_codes
langCodes = {
	'ab': 'ab', # Abkhazian
	'ace': 'ace',
	'af': 'af',
	'ak': 'ak',
	'aln': 'aln',
	'als': 'gsw', # Swiss German (Alsatian/Alemannic)
	'am': 'am',
	'an': 'an',
	'ang': 'ang',
	'ar': 'ar',
	'arc': 'arc',
	'arz': 'arz',
	'as': 'as',
	'ast': 'ast',
	'av': 'av',
	'avk': 'avk',
	'ay': 'ay',
	'az': 'az',
	'ba': 'ba',
	'bar': 'bar',
	'bat-smg': 'sgs', #TODO might be redundant (Samogitian)
	'bcl': 'bcl',
	'be': 'be',
	'be-tarask': 'be-tarask', # Belarusian in Taraskievica orthography
	'be-x-old': 'be-tarask', #TODO might be redundant
	'bg': 'bg',
	'bh': 'bh',
	'bi': 'bi',
	'bjn': 'bjn',
	'bm': 'bm',
	'bn': 'bn',
	'bo': 'bo',
	'bpy': 'bpy',
	'br': 'br',
	'bs': 'bs',
	'bug': 'bug',
	'bxr': 'bxr',
	'ca': 'ca',
	'cbk-zam': 'cbk-x-zam', # Chavacano de Zamboanga
	'cdo': 'cdo',
	'ceb': 'ceb',
	'ce': 'ce',
	'ch': 'ch',
	'chr': 'chr',
	'chy': 'chy',
	'ckb': 'ckb',
	'co': 'co',
	'cr': 'cr',
	'crh': 'crh-Latn', #TODO might be redundant
	'crh-latn': 'crh-Latn', # Crimean Tatar/Crimean Turkish; script Latin
	'csb': 'csb',
	'cs': 'cs',
	'cu': 'cu',
	'cv': 'cv',
	'cy': 'cy',
	'da': 'da',
	'de-at': 'de-AT', # German, Austria
	'de-ch': 'de-CH', # German, Switzerland
	'de': 'de', # German
	'de-formal': 'de-x-formal',  # custom private subtag for formal German
	'diq': 'diq',
	'dsb': 'dsb',
	'dv': 'dv',
	'dz': 'dz',
	'ee': 'ee',
	'egl': 'egl',
	'el': 'el',
	'eml': 'eml', # Emilian-Romagnol; 'eml' is now retired and split into egl (Emilian) and rgn (Romagnol), but eml will remain a valid BCP 47 language tag indefinitely (see bugzilla:34217)
	'en-ca': 'en-CA', # English; Canada
	'en': 'en', # English
	'en-gb': 'en-GB', # English; Great Britain
	'eo': 'eo', # Esperanto
	'es': 'es',
	'et': 'et',
	'eu': 'eu',
	'ext': 'ext',
	'fa': 'fa',
	'ff': 'ff',
	'fi': 'fi',
	'fiu-vro': 'vro', #TODO might be redundant
	'fj': 'fj',
	'fo': 'fo',
	'frc': 'frc',
	'fr': 'fr',
	'frp': 'frp',
	'frr': 'frr',
	'fur': 'fur',
	'fy': 'fy',
	'ga': 'ga',
	'gag': 'gag',
	'gan': 'gan', # Gan Chinese; TODO which script?
	'gan-hans': 'gan-Hans', # Gan Chinese; script Han (simplified)
	'gan-hant': 'gan-Hant', # Gan Chinese; script Han (traditional)
	'gd': 'gd',
	'gl': 'gl',
	'glk': 'glk',
	'gn': 'gn',
	'got': 'got',
	'gsw': 'gsw',
	'gu': 'gu',
	'gv': 'gv',
	'ha': 'ha',
	'hak': 'hak',
	'haw': 'haw',
	'he': 'he',
	'hif': 'hif',
	'hi': 'hi',
	'ho': 'ho',
	'hr': 'hr',
	'hsb': 'hsb',
	'ht': 'ht',
	'hu': 'hu',
	'hy': 'hy',
	'ia': 'ia',
	'id': 'id',
	'ie': 'ie',
	'ig': 'ig',
	'ike-cans': 'ike-Cans', # Eastern Canadian Inuktitut, Unified Canadian Aboriginal Syllabics script
	'ike-latn': 'ike-Latn', # Eastern Canadian Inuktitut, Latin script
	'ik': 'ik',
	'ilo': 'ilo',
	'io': 'io',
	'is': 'is',
	'it': 'it',
	'iu': 'iu',
	'ja': 'ja',
	'jam': 'jam',
	'jbo': 'jbo',
	'jut': 'jut',
	'jv': 'jv',
	'kaa': 'kaa',
	'kab': 'kab',
	'ka': 'ka',
	'kbd': 'kbd',
	'kg': 'kg',
	'ki': 'ki',
	'kiu': 'kiu',
	'kk-arab': 'kk-Arab',# Kazakh; script Arabic
	'kk-cn': 'kk-CN', # Kazakh; PR China
	'kk-cyrl': 'kk-Cyrl', # Kazakh; script Cyrillic; TODO IANA has kk with Suppress-Script: Cyrl, so it should be the same as kk
	'kk': 'kk', # Kazakh
	'kk-kz': 'kk-KZ', # Kazakh; Kazakhstan
	'kk-latn': 'kk-Latn', # Kazakh; script Latin
	'kk-tr': 'kk-TR', # Kazakh; Turkey
	'kl': 'kl',
	'km': 'km',
	'kn': 'kn',
	'koi': 'koi',
	'ko': 'ko',
	'krc': 'krc',
	'krj': 'krj',
	'ksh': 'mis-x-rip', # Ripuarian (the code "ksh" refers to Koelsch, a subset of Ripuarian)
	'ks': 'ks',
	'ku-arab': 'ku-Arab', # Kurdish; script Arabic
	'ku': 'ku', # Kurdish; TODO this is a macrolanguage; anything more specific? TODO all uses seem to be in Latin -- should this be ku-Latn then?
	'ku-latn': 'ku-Latn', # Kurdish; script Latin
	'kv': 'kv',
	'kw': 'kw',
	'ky': 'ky',
	'lad': 'lad',
	'la': 'la',
	'lbe': 'lbe',
	'lb': 'lb',
	'lez': 'lez',
	'lfn': 'lfn',
	'lg': 'lg',
	'lij': 'lij',
	'li': 'li',
	'liv': 'liv',
	'lmo': 'lmo',
	'ln': 'ln',
	'lo': 'lo',
	'ltg': 'ltg',
	'lt': 'lt',
	'lv': 'lv',
	'lzh': 'lzh', # Literary Chinese
	'map-bms': 'jv-x-bms', # Basa Banyumasan has no code; jv is a superset (Javanese)
	'mdf': 'mdf',
	'mg': 'mg',
	'mhr': 'mhr',
	'mi': 'mi',
	'min': 'min',
	'mk': 'mk',
	'ml': 'ml',
	'mn': 'mn',
	'mo': 'mo',
	'mrj': 'mrj',
	'mr': 'mr',
	'ms': 'ms',
	'mt': 'mt',
	'mwl': 'mwl',
	'my': 'my',
	'myv': 'myv',
	'mzn': 'mzn',
	'nah': 'nah',
	'na': 'na',
	'nan': 'nan',
	'nap': 'nap',
	'nb': 'nb',
	'nds': 'nds', # Low German
	'nds-nl': 'nds-NL', # Low German, Netherlands; TODO might be redundant (nds might be the same)
	'ne': 'ne',
	'new': 'new',
	'ng': 'ng',
	'nl-informal': 'nl-x-informal', # custom private subtag for informal Dutch
	'nl': 'nl',
	'nn': 'nn',
	'no': 'no', # TODO possibly this is "nb" (Norwegian Bokmål); but current dumps have different values for "nb" and "no" in some cases
	'nov': 'nov',
	'nrm': 'fr-x-nrm', # Norman; no individual code; lumped with French in ISO 639/3
	'nso': 'nso',
	'nv': 'nv',
	'ny': 'ny',
	'oc': 'oc',
	'om': 'om',
	'or': 'or',
	'os': 'os',
	'pag': 'pag',
	'pam': 'pam',
	'pa': 'pa',
	'pap': 'pap',
	'pcd': 'pcd',
	'pdc': 'pdc',
	'pfl': 'pfl',
	'pih': 'pih',
	'pi': 'pi',
	'pl': 'pl',
	'pms': 'pms',
	'pnb': 'pnb',
	'pnt': 'pnt',
	'ps': 'ps',
	'pt-br': 'pt-BR', # Portuguese, Brazil
	'pt': 'pt', # Portuguese
	'qu': 'qu',
	'rm': 'rm',
	'rmy': 'rmy',
	'rn': 'rn',
	'roa-rup': 'rup', # TODO might be redundant
	'roa-tara': 'it-x-tara', # Tarantino; no language code, ISO 639-3 lumps it with Italian
	'ro': 'ro',
	'rue': 'rue',
	'rup': 'rup', # Macedo-Romanian/Aromanian
	'ru': 'ru',
	'rw': 'rw',
	'sah': 'sah',
	'sa': 'sa',
	'scn': 'scn',
	'sco': 'sco',
	'sc': 'sc',
	'sd': 'sd',
	'se': 'se',
	'sg': 'sg',
	'sgs': 'sgs',
	'shi': 'shi',
	'sh': 'sh', # Serbo-Croatian; macrolanguage, not modern but a valid BCP 47 tag
	'simple': 'en-x-simple', # custom private subtag for simple English
	'si': 'si',
	'sk': 'sk',
	'sl': 'sl',
	'sma': 'sma',
	'sm': 'sm',
	'sn': 'sn',
	'so': 'so',
	'sq': 'sq',
	'sr-ec': 'sr-Cyrl', # Serbian; Cyrillic script (might change if dialect codes are added to IANA)
	'sr-el': 'sr-Latn', # Serbian; Latin script (might change if dialect codes are added to IANA)
	'srn': 'srn',
	'sr': 'sr', # Serbian TODO should probably be sr-Cyrl too?
	'ss': 'ss',
	'stq': 'stq',
	'st': 'st',
	'su': 'su',
	'sv': 'sv',
	'sw': 'sw',
	'szl': 'szl',
	'ta': 'ta',
	'te': 'te',
	'tet': 'tet',
	'tg-latn': 'tg-Latn', # Tajik; script Latin
	'tg': 'tg',
	'th': 'th',
	'ti': 'ti',
	'tk': 'tk',
	'tl': 'tl',
	'tn': 'tn',
	'tokipona': 'mis-x-tokipona', # Tokipona, a constructed language without a code
	'to': 'to',
	'tpi': 'tpi',
	'tr': 'tr',
	'ts': 'ts',
	'tt': 'tt',
	'tum': 'tum',
	'tw': 'tw',
	'ty': 'ty',
	'tyv': 'tyv',
	'udm': 'udm',
	'ug': 'ug',
	'uk': 'uk',
	'ur': 'ur',
	'uz': 'uz',
	'vec': 'vec',
	'vep': 'vep',
	've': 've',
	'vi': 'vi',
	'vls': 'vls',
	'vmf': 'vmf',
	'vo': 'vo',
	'vro': 'vro',
	'war': 'war',
	'wa': 'wa',
	'wo': 'wo',
	'wuu': 'wuu',
	'xal': 'xal',
	'xh': 'xh',
	'xmf': 'xmf',
	'yi': 'yi',
	'yo': 'yo',
	'yue': 'yue', # Cantonese
	'za': 'za',
	'zea': 'zea',
	'zh-classical': 'lzh', # TODO might be redundant
	'zh-cn': 'zh-CN', # Chinese, PRC
	'zh-hans': 'zh-Hans', # Chinese; script Han (simplified)
	'zh-hant': 'zh-Hant', # Chinese; script Han (traditional)
	'zh-hk': 'zh-HK', # Chinese, Hong Kong
	'zh-min-nan': 'nan', # TODO might be redundant
	'zh-mo': 'zh-MO', # Chinese, Macao
	'zh-my': 'zh-MY', # Chinese, Malaysia
	'zh-sg': 'zh-SG', # Chinese, Singapore
	'zh-tw': 'zh-TW', # Chinese, Taiwan, Province of China
	'zh-yue': 'yue', # TODO might be redundant
	'zh': 'zh', # Chinese; TODO zh is a macrolanguage; should this be cmn? Also, is this the same as zh-Hans or zh-Hant?
	'zu': 'zu' # Zulu
}

# The languages used on sites linked from Wikidata in terms of
# BCP 47 http://www.rfc-editor.org/rfc/bcp/bcp47.txt.
# Exceptional Wikipedia language codes are documented at
# http://meta.wikimedia.org/wiki/Special_language_codes
siteLanguageCodes = {
	'aawiki' : 'aa',
	'abwiki' : 'ab',
	'acewiki' : 'ace',
	'afwiki' : 'af',
	'akwiki' : 'ak',
	'alswiki' : 'gsw', # Swiss German (Alsatian/Alemannic)
	'amwiki' : 'am',
	'angwiki' : 'ang',
	'anwiki' : 'an',
	'arcwiki' : 'arc',
	'arwiki' : 'ar',
	'arzwiki' : 'arz',
	'astwiki' : 'ast',
	'aswiki' : 'as',
	'avwiki' : 'av',
	'aywiki' : 'ay',
	'azwiki' : 'az',
	'barwiki' : 'bar',
	'bat_smgwiki' : 'sgs', # Samogitian
	'bawiki' : 'ba',
	'bclwiki' : 'bcl',
	'be_x_oldwiki' : 'be-tarask', # Belarusian in Taraskievica orthography
	'bewiki' : 'be',
	'bgwiki' : 'bg',
	'bhwiki' : 'bh',
	'biwiki' : 'bi',
	'bjnwiki' : 'bjn',
	'bmwiki' : 'bm',
	'bnwiki' : 'bn',
	'bowiki' : 'bo',
	'bpywiki' : 'bpy',
	'brwiki' : 'br',
	'bswiki' : 'bs',
	'bugwiki' : 'bug',
	'bxrwiki' : 'bxr',
	'cawiki' : 'ca',
	'cbk_zamwiki' : 'cbk-x-zam', # Chavacano de Zamboanga
	'cdowiki' : 'cdo',
	'cebwiki' : 'ceb',
	'cewiki' : 'ce',
	'chowiki' : 'cho',
	'chrwiki' : 'chr',
	'chwiki' : 'ch',
	'chywiki' : 'chy',
	'ckbwiki' : 'ckb',
	'cowiki' : 'co',
	'crhwiki' : 'crh-Latn', # Crimean Tatar/Crimean Turkish in Latin script
	'crwiki' : 'cr',
	'csbwiki' : 'csb',
	'cswiki' : 'cs',
	'cuwiki' : 'cu',
	'cvwiki' : 'cv',
	'cywiki' : 'cy',
	'dawiki' : 'da',
	'dewiki' : 'de',
	'dewikivoyage' : 'de',
	'diqwiki' : 'diq',
	'dsbwiki' : 'dsb',
	'dvwiki' : 'dv',
	'dzwiki' : 'dz',
	'eewiki' : 'ee',
	'elwiki' : 'el',
	'elwikivoyage' : 'el',
	'emlwiki' : 'eml',
	'enwiki' : 'en',
	'enwikivoyage' : 'en',
	'eowiki' : 'eo',
	'eswiki' : 'es',
	'eswikivoyage' : 'es',
	'etwiki' : 'et',
	'euwiki' : 'eu',
	'extwiki' : 'ext',
	'fawiki' : 'fa',
	'ffwiki' : 'ff',
	'fiu_vrowiki' : 'vro', # Võro
	'fiwiki' : 'fi',
	'fjwiki' : 'fj',
	'fowiki' : 'fo',
	'frpwiki' : 'frp',
	'frrwiki' : 'frr',
	'frwiki' : 'fr',
	'frwikivoyage' : 'fr',
	'furwiki' : 'fur',
	'fywiki' : 'fy',
	'gagwiki' : 'gag',
	'ganwiki' : 'gan',
	'gawiki' : 'ga',
	'gdwiki' : 'gd',
	'glkwiki' : 'glk',
	'glwiki' : 'gl',
	'gnwiki' : 'gn',
	'gotwiki' : 'got',
	'guwiki' : 'gu',
	'gvwiki' : 'gv',
	'hakwiki' : 'hak',
	'hawiki' : 'ha',
	'hawwiki' : 'haw',
	'hewiki' : 'he',
	'hewikivoyage' : 'he',
	'hifwiki' : 'hif',
	'hiwiki' : 'hi',
	'howiki' : 'ho',
	'hrwiki' : 'hr',
	'hsbwiki' : 'hsb',
	'htwiki' : 'ht',
	'huwiki' : 'hu',
	'hywiki' : 'hy',
	'hzwiki' : 'hz',
	'iawiki' : 'ia',
	'idwiki' : 'id',
	'iewiki' : 'ie',
	'igwiki' : 'ig',
	'iiwiki' : 'ii',
	'ikwiki' : 'ik',
	'ilowiki' : 'ilo',
	'iowiki' : 'io',
	'iswiki' : 'is',
	'itwiki' : 'it',
	'itwikivoyage' : 'it',
	'iuwiki' : 'iu',
	'jawiki' : 'ja',
	'jbowiki' : 'jbo',
	'jvwiki' : 'jv',
	'kaawiki' : 'kaa',
	'kabwiki' : 'kab',
	'kawiki' : 'ka',
	'kbdwiki' : 'kbd',
	'kgwiki' : 'kg',
	'kiwiki' : 'ki',
	'kjwiki' : 'kj',
	'kkwiki' : 'kk',
	'klwiki' : 'kl',
	'kmwiki' : 'km',
	'knwiki' : 'kn',
	'koiwiki' : 'koi',
	'kowiki' : 'ko',
	'krcwiki' : 'krc',
	'krwiki' : 'kr',
	'kshwiki' : 'mis-x-rip', # Ripuarian (the code "ksh" refers to Koelsch, a subset of Ripuarian)
	'kswiki' : 'ks',
	'kuwiki' : 'ku',
	'kvwiki' : 'kv',
	'kwwiki' : 'kw',
	'kywiki' : 'ky',
	'ladwiki' : 'lad',
	'lawiki' : 'la',
	'lbewiki' : 'lbe',
	'lbwiki' : 'lb',
	'lezwiki' : 'lez',
	'lgwiki' : 'lg',
	'lijwiki' : 'lij',
	'liwiki' : 'li',
	'lmowiki' : 'lmo',
	'lnwiki' : 'ln',
	'lowiki' : 'lo',
	'ltgwiki' : 'ltg',
	'ltwiki' : 'lt',
	'lvwiki' : 'lv',
	'map_bmswiki' : 'jv-x-bms', # Basa Banyumasan has no code; jv is a superset (Javanese)
	'mdfwiki' : 'mdf',
	'mgwiki' : 'mg',
	'mhrwiki' : 'mhr',
	'mhwiki' : 'mh',
	'minwiki' : 'min',
	'miwiki' : 'mi',
	'mkwiki' : 'mk',
	'mlwiki' : 'ml',
	'mnwiki' : 'mn',
	'mowiki' : 'mo',
	'mrjwiki' : 'mrj',
	'mrwiki' : 'mr',
	'mswiki' : 'ms',
	'mtwiki' : 'mt',
	'muswiki' : 'mus',
	'mwlwiki' : 'mwl',
	'myvwiki' : 'myv',
	'mywiki' : 'my',
	'mznwiki' : 'mzn',
	'nahwiki' : 'nah',
	'napwiki' : 'nap',
	'nawiki' : 'na',
	'nds_nlwiki' : 'nds-NL', # Low German, Netherlands; TODO might be redundant (nds might be the same)
	'ndswiki' : 'nds',
	'newiki' : 'ne',
	'newwiki' : 'new',
	'ngwiki' : 'ng',
	'nlwiki' : 'nl',
	'nlwikivoyage' : 'nl',
	'nnwiki' : 'nn',
	'novwiki' : 'nov',
	'nowiki' : 'nb', # Norwegian Bokmål
	'nrmwiki' : 'fr-x-nrm', # Norman; no individual code; lumped with French in ISO 639/3
	'nsowiki' : 'nso',
	'nvwiki' : 'nv',
	'nywiki' : 'ny',
	'ocwiki' : 'oc',
	'omwiki' : 'om',
	'orwiki' : 'or',
	'oswiki' : 'os',
	'pagwiki' : 'pag',
	'pamwiki' : 'pam',
	'papwiki' : 'pap',
	'pawiki' : 'pa',
	'pcdwiki' : 'pcd',
	'pdcwiki' : 'pdc',
	'pflwiki' : 'pfl',
	'pihwiki' : 'pih',
	'piwiki' : 'pi',
	'plwiki' : 'pl',
	'plwikivoyage' : 'pl',
	'pmswiki' : 'pms',
	'pnbwiki' : 'pnb',
	'pntwiki' : 'pnt',
	'pswiki' : 'ps',
	'ptwiki' : 'pt',
	'ptwikivoyage' : 'pt',
	'quwiki' : 'qu',
	'rmwiki' : 'rm',
	'rmywiki' : 'rmy',
	'rnwiki' : 'rn',
	'roa_rupwiki' : 'rup', # Macedo-Romanian/Aromanian
	'roa_tarawiki' : 'it-x-tara', # Tarantino; no language code, ISO 639-3 lumps it with Italian
	'rowiki' : 'ro',
	'rowikivoyage' : 'ro',
	'ruewiki' : 'rue',
	'ruwiki' : 'ru',
	'ruwikivoyage' : 'ru',
	'rwwiki' : 'rw',
	'sahwiki' : 'sah',
	'sawiki' : 'sa',
	'scnwiki' : 'scn',
	'scowiki' : 'sco',
	'scwiki' : 'sc',
	'sdwiki' : 'sd',
	'sewiki' : 'se',
	'sgwiki' : 'sg',
	'shwiki' : 'sh', # Serbo-Croatian; macrolanguage, not modern but a valid BCP 47 tag
	'simplewiki' : 'en',
	'siwiki' : 'si',
	'skwiki' : 'sk',
	'slwiki' : 'sl',
	'smwiki' : 'sm',
	'snwiki' : 'sn',
	'sowiki' : 'so',
	'sqwiki' : 'sq',
	'srnwiki' : 'srn',
	'srwiki' : 'sr',
	'sswiki' : 'ss',
	'stqwiki' : 'stq',
	'stwiki' : 'st',
	'suwiki' : 'su',
	'svwiki' : 'sv',
	'svwikivoyage' : 'sv',
	'swwiki' : 'sw',
	'szlwiki' : 'szl',
	'tawiki' : 'ta',
	'tetwiki' : 'tet',
	'tewiki' : 'te',
	'tgwiki' : 'tg',
	'thwiki' : 'th',
	'tiwiki' : 'ti',
	'tkwiki' : 'tk',
	'tlwiki' : 'tl',
	'tnwiki' : 'tn',
	'towiki' : 'to',
	'tpiwiki' : 'tpi',
	'trwiki' : 'tr',
	'tswiki' : 'ts',
	'ttwiki' : 'tt',
	'tumwiki' : 'tum',
	'twwiki' : 'tw',
	'tywiki' : 'ty',
	'tyvwiki' : 'tyv',
	'udmwiki' : 'udm',
	'ugwiki' : 'ug',
	'ukwiki' : 'uk',
	'ukwikivoyage' : 'uk',
	'urwiki' : 'ur',
	'uzwiki' : 'uz',
	'vecwiki' : 'vec',
	'vepwiki' : 'vep',
	'vewiki' : 've',
	'viwiki' : 'vi',
	'viwikivoyage' : 'vi',
	'vlswiki' : 'vls',
	'vowiki' : 'vo',
	'warwiki' : 'war',
	'wawiki' : 'wa',
	'wowiki' : 'wo',
	'wuuwiki' : 'wuu',
	'xalwiki' : 'xal',
	'xhwiki' : 'xh',
	'xmfwiki' : 'xmf',
	'yiwiki' : 'yi',
	'yowiki' : 'yo',
	'zawiki' : 'za',
	'zeawiki' : 'zea',
	'zh_classicalwiki' : 'lzh', # Literary Chinese
	'zh_min_nanwiki' : 'nan', # Min Nan Chinese
	'zh_yuewiki' : 'yue', # Cantonese
	'zhwiki' : 'zh', # TODO zh is a macrolanguage; should this be cmn?
	'zuwiki' : 'zu'
}

# Local cache for property types, to avoid having to fetch any
# from the Web if there is no sufficient type information in the
# dump before we first need it.
# This list can be extended by any valid property type -- types
# never change, so the information does not get outdated.
knownPropertyTypes = {
        'P10' : 'commonsMedia', 'P1001' : 'wikibase-item', 'P1002' : 'wikibase-item', 'P1003' : 'string',
        'P1004' : 'string', 'P1005' : 'string', 'P1006' : 'string', 'P101' : 'wikibase-item',
        'P1014' : 'string', 'P1015' : 'string', 'P1016' : 'wikibase-item', 'P1017' : 'string',
        'P1018' : 'wikibase-item', 'P1019' : 'url', 'P102' : 'wikibase-item', 'P1027' : 'wikibase-item',
        'P1029' : 'wikibase-item', 'P103' : 'wikibase-item', 'P1031' : 'string', 'P1036' : 'string',
        'P1038' : 'wikibase-item', 'P1039' : 'wikibase-item', 'P1040' : 'wikibase-item', 'P1042' : 'string',
        'P1044' : 'string', 'P1046' : 'wikibase-item', 'P1047' : 'string', 'P1048' : 'string',
        'P1049' : 'wikibase-item', 'P105' : 'wikibase-item', 'P1050' : 'wikibase-item', 'P1052' : 'string',
        'P106' : 'wikibase-item', 'P107' : 'wikibase-item', 'P108' : 'wikibase-item', 'P109' : 'commonsMedia',
        'P110' : 'wikibase-item', 'P111' : 'wikibase-item', 'P112' : 'wikibase-item', 'P113' : 'wikibase-item',
        'P114' : 'wikibase-item', 'P115' : 'wikibase-item', 'P117' : 'commonsMedia', 'P118' : 'wikibase-item',
        'P119' : 'wikibase-item', 'P121' : 'wikibase-item', 'P122' : 'wikibase-item', 'P123' : 'wikibase-item',
        'P126' : 'wikibase-item', 'P127' : 'wikibase-item', 'P128' : 'wikibase-item', 'P129' : 'wikibase-item',
        'P131' : 'wikibase-item', 'P132' : 'wikibase-item', 'P133' : 'wikibase-item', 'P134' : 'wikibase-item',
        'P135' : 'wikibase-item', 'P136' : 'wikibase-item', 'P137' : 'wikibase-item', 'P138' : 'wikibase-item',
        'P14' : 'commonsMedia', 'P140' : 'wikibase-item', 'P141' : 'wikibase-item', 'P143' : 'wikibase-item',
        'P144' : 'wikibase-item', 'P149' : 'wikibase-item', 'P15' : 'commonsMedia', 'P150' : 'wikibase-item',
        'P154' : 'commonsMedia', 'P155' : 'wikibase-item', 'P156' : 'wikibase-item', 'P157' : 'wikibase-item',
        'P158' : 'commonsMedia', 'P159' : 'wikibase-item', 'P16' : 'wikibase-item', 'P160' : 'wikibase-item',
        'P161' : 'wikibase-item', 'P162' : 'wikibase-item', 'P163' : 'wikibase-item', 'P166' : 'wikibase-item',
        'P168' : 'wikibase-item', 'P169' : 'wikibase-item', 'P17' : 'wikibase-item', 'P170' : 'wikibase-item',
        'P171' : 'wikibase-item', 'P172' : 'wikibase-item', 'P173' : 'wikibase-item', 'P175' : 'wikibase-item',
        'P176' : 'wikibase-item', 'P177' : 'wikibase-item', 'P178' : 'wikibase-item', 'P179' : 'wikibase-item',
        'P18' : 'commonsMedia', 'P180' : 'wikibase-item', 'P181' : 'commonsMedia', 'P183' : 'wikibase-item',
        'P184' : 'wikibase-item', 'P185' : 'wikibase-item', 'P186' : 'wikibase-item', 'P189' : 'wikibase-item',
        'P19' : 'wikibase-item', 'P190' : 'wikibase-item', 'P193' : 'wikibase-item', 'P194' : 'wikibase-item',
        'P195' : 'wikibase-item', 'P196' : 'wikibase-item', 'P197' : 'wikibase-item', 'P198' : 'wikibase-item',
        'P199' : 'wikibase-item', 'P20' : 'wikibase-item', 'P200' : 'wikibase-item', 'P201' : 'wikibase-item',
        'P202' : 'wikibase-item', 'P205' : 'wikibase-item', 'P206' : 'wikibase-item', 'P208' : 'wikibase-item',
        'P209' : 'wikibase-item', 'P21' : 'wikibase-item', 'P212' : 'string', 'P213' : 'string',
        'P214' : 'string', 'P215' : 'string', 'P217' : 'string', 'P218' : 'string',
        'P219' : 'string', 'P22' : 'wikibase-item', 'P220' : 'string', 'P223' : 'string',
        'P225' : 'string', 'P227' : 'string', 'P229' : 'string', 'P230' : 'string',
        'P231' : 'string', 'P232' : 'string', 'P233' : 'string', 'P234' : 'string',
        'P235' : 'string', 'P236' : 'string', 'P237' : 'wikibase-item', 'P238' : 'string',
        'P239' : 'string', 'P240' : 'string', 'P241' : 'wikibase-item', 'P242' : 'commonsMedia',
        'P243' : 'string', 'P244' : 'string', 'P245' : 'string', 'P246' : 'string',
        'P247' : 'string', 'P248' : 'wikibase-item', 'P249' : 'string', 'P25' : 'wikibase-item',
        'P26' : 'wikibase-item', 'P263' : 'wikibase-item', 'P264' : 'wikibase-item', 'P267' : 'string',
        'P268' : 'string', 'P269' : 'string', 'P27' : 'wikibase-item', 'P270' : 'string',
        'P271' : 'string', 'P272' : 'wikibase-item', 'P273' : 'wikibase-item', 'P274' : 'string',
        'P275' : 'wikibase-item', 'P276' : 'wikibase-item', 'P277' : 'wikibase-item', 'P278' : 'string',
        'P279' : 'wikibase-item', 'P281' : 'string', 'P282' : 'wikibase-item', 'P286' : 'wikibase-item',
        'P287' : 'wikibase-item', 'P289' : 'wikibase-item', 'P291' : 'wikibase-item', 'P295' : 'wikibase-item',
        'P296' : 'string', 'P297' : 'string', 'P298' : 'string', 'P299' : 'string',
        'P30' : 'wikibase-item', 'P300' : 'string', 'P301' : 'wikibase-item', 'P304' : 'string',
        'P305' : 'string', 'P306' : 'wikibase-item', 'P31' : 'wikibase-item', 'P344' : 'wikibase-item',
        'P345' : 'string', 'P347' : 'string', 'P348' : 'string', 'P349' : 'string',
        'P35' : 'wikibase-item', 'P351' : 'string', 'P352' : 'string', 'P353' : 'string',
        'P354' : 'string', 'P355' : 'wikibase-item', 'P356' : 'string', 'P357' : 'string',
        'P358' : 'wikibase-item', 'P359' : 'string', 'P36' : 'wikibase-item', 'P360' : 'wikibase-item',
        'P361' : 'wikibase-item', 'P364' : 'wikibase-item', 'P366' : 'wikibase-item', 'P367' : 'commonsMedia',
        'P37' : 'wikibase-item', 'P370' : 'string', 'P371' : 'wikibase-item', 'P373' : 'string',
        'P374' : 'string', 'P375' : 'wikibase-item', 'P376' : 'wikibase-item', 'P377' : 'string',
        'P38' : 'wikibase-item', 'P380' : 'string', 'P381' : 'string', 'P382' : 'string',
        'P387' : 'string', 'P39' : 'wikibase-item', 'P392' : 'string', 'P393' : 'string',
        'P395' : 'string', 'P396' : 'string', 'P397' : 'wikibase-item', 'P398' : 'wikibase-item',
        'P399' : 'wikibase-item', 'P40' : 'wikibase-item', 'P400' : 'wikibase-item', 'P402' : 'string',
        'P403' : 'wikibase-item', 'P404' : 'wikibase-item', 'P405' : 'wikibase-item', 'P406' : 'wikibase-item',
        'P407' : 'wikibase-item', 'P408' : 'wikibase-item', 'P409' : 'string', 'P41' : 'commonsMedia',
        'P410' : 'wikibase-item', 'P411' : 'wikibase-item', 'P412' : 'wikibase-item', 'P413' : 'wikibase-item',
        'P414' : 'wikibase-item', 'P416' : 'string', 'P417' : 'wikibase-item', 'P418' : 'wikibase-item',
        'P421' : 'wikibase-item', 'P423' : 'wikibase-item', 'P424' : 'string', 'P425' : 'wikibase-item',
        'P427' : 'wikibase-item', 'P428' : 'string', 'P429' : 'string', 'P43' : 'wikibase-item',
        'P432' : 'string', 'P433' : 'string', 'P434' : 'string', 'P435' : 'string',
        'P436' : 'string', 'P437' : 'wikibase-item', 'P438' : 'string', 'P439' : 'string',
        'P44' : 'wikibase-item', 'P440' : 'string', 'P442' : 'string', 'P443' : 'commonsMedia',
        'P444' : 'string', 'P447' : 'wikibase-item', 'P448' : 'wikibase-item', 'P449' : 'wikibase-item',
        'P45' : 'wikibase-item', 'P450' : 'wikibase-item', 'P451' : 'wikibase-item', 'P452' : 'wikibase-item',
        'P453' : 'wikibase-item', 'P454' : 'string', 'P455' : 'string', 'P457' : 'wikibase-item',
        'P459' : 'wikibase-item', 'P460' : 'wikibase-item', 'P461' : 'wikibase-item', 'P462' : 'wikibase-item',
        'P463' : 'wikibase-item', 'P465' : 'string', 'P466' : 'wikibase-item', 'P467' : 'wikibase-item',
        'P469' : 'wikibase-item', 'P47' : 'wikibase-item', 'P470' : 'wikibase-item', 'P473' : 'string',
        'P474' : 'string', 'P476' : 'string', 'P477' : 'string', 'P478' : 'string',
        'P480' : 'string', 'P483' : 'wikibase-item', 'P484' : 'string', 'P485' : 'wikibase-item',
        'P486' : 'string', 'P487' : 'string', 'P488' : 'wikibase-item', 'P489' : 'wikibase-item',
        'P490' : 'string', 'P491' : 'commonsMedia', 'P492' : 'string', 'P493' : 'string',
        'P494' : 'string', 'P495' : 'wikibase-item', 'P498' : 'string', 'P50' : 'wikibase-item',
        'P500' : 'wikibase-item', 'P501' : 'wikibase-item', 'P503' : 'string', 'P504' : 'wikibase-item',
        'P506' : 'string', 'P507' : 'string', 'P508' : 'string', 'P509' : 'wikibase-item',
        'P51' : 'commonsMedia', 'P511' : 'wikibase-item', 'P512' : 'wikibase-item', 'P513' : 'string',
        'P516' : 'wikibase-item', 'P517' : 'wikibase-item', 'P518' : 'wikibase-item', 'P520' : 'wikibase-item',
        'P522' : 'wikibase-item', 'P523' : 'wikibase-item', 'P524' : 'wikibase-item', 'P525' : 'string',
        'P527' : 'wikibase-item', 'P528' : 'string', 'P529' : 'string', 'P53' : 'wikibase-item',
        'P530' : 'wikibase-item', 'P531' : 'wikibase-item', 'P534' : 'wikibase-item', 'P535' : 'string',
        'P536' : 'string', 'P54' : 'wikibase-item', 'P542' : 'wikibase-item', 'P543' : 'wikibase-item',
        'P545' : 'wikibase-item', 'P547' : 'wikibase-item', 'P549' : 'string', 'P551' : 'wikibase-item',
        'P552' : 'wikibase-item', 'P553' : 'wikibase-item', 'P554' : 'string', 'P555' : 'string',
        'P556' : 'wikibase-item', 'P557' : 'string', 'P558' : 'string', 'P559' : 'wikibase-item',
        'P560' : 'wikibase-item', 'P561' : 'string', 'P562' : 'wikibase-item', 'P563' : 'string',
        'P564' : 'string', 'P566' : 'wikibase-item', 'P568' : 'wikibase-item', 'P569' : 'time',
        'P57' : 'wikibase-item', 'P570' : 'time', 'P571' : 'time', 'P574' : 'time',
        'P575' : 'time', 'P576' : 'time', 'P577' : 'time', 'P579' : 'wikibase-item',
        'P58' : 'wikibase-item', 'P580' : 'time', 'P582' : 'time', 'P585' : 'time',
        'P586' : 'string', 'P588' : 'wikibase-item', 'P589' : 'wikibase-item', 'P59' : 'wikibase-item',
        'P590' : 'string', 'P592' : 'string', 'P593' : 'string', 'P594' : 'string',
        'P595' : 'string', 'P597' : 'string', 'P598' : 'wikibase-item', 'P599' : 'string',
        'P6' : 'wikibase-item', 'P60' : 'wikibase-item', 'P600' : 'string', 'P604' : 'string',
        'P605' : 'string', 'P606' : 'time', 'P607' : 'wikibase-item', 'P608' : 'wikibase-item',
        'P609' : 'wikibase-item', 'P61' : 'wikibase-item', 'P610' : 'wikibase-item', 'P611' : 'wikibase-item',
        'P612' : 'wikibase-item', 'P613' : 'string', 'P618' : 'wikibase-item', 'P619' : 'time',
        'P624' : 'wikibase-item', 'P625' : 'globe-coordinate', 'P627' : 'string', 'P628' : 'string',
        'P629' : 'wikibase-item', 'P630' : 'string', 'P631' : 'wikibase-item', 'P634' : 'wikibase-item',
        'P635' : 'string', 'P637' : 'string', 'P638' : 'string', 'P639' : 'string',
        'P640' : 'string', 'P641' : 'wikibase-item', 'P642' : 'wikibase-item', 'P643' : 'string',
        'P644' : 'string', 'P645' : 'string', 'P646' : 'string', 'P647' : 'wikibase-item',
        'P648' : 'string', 'P649' : 'string', 'P65' : 'wikibase-item', 'P651' : 'string',
        'P652' : 'string', 'P653' : 'string', 'P654' : 'wikibase-item', 'P655' : 'wikibase-item',
        'P657' : 'string', 'P658' : 'wikibase-item', 'P66' : 'wikibase-item', 'P660' : 'wikibase-item',
        'P661' : 'string', 'P662' : 'string', 'P664' : 'wikibase-item', 'P667' : 'string',
        'P668' : 'string', 'P669' : 'wikibase-item', 'P670' : 'string', 'P672' : 'string',
        'P673' : 'string', 'P674' : 'wikibase-item', 'P676' : 'wikibase-item', 'P680' : 'wikibase-item',
        'P681' : 'wikibase-item', 'P682' : 'wikibase-item', 'P683' : 'string', 'P684' : 'wikibase-item',
        'P685' : 'string', 'P686' : 'string', 'P687' : 'string', 'P688' : 'wikibase-item',
        'P689' : 'wikibase-item', 'P69' : 'wikibase-item', 'P690' : 'wikibase-item', 'P691' : 'string',
        'P695' : 'string', 'P696' : 'string', 'P697' : 'wikibase-item', 'P699' : 'string',
        'P7' : 'wikibase-item', 'P70' : 'wikibase-item', 'P700' : 'string', 'P702' : 'wikibase-item',
        'P703' : 'wikibase-item', 'P704' : 'string', 'P705' : 'string', 'P706' : 'wikibase-item',
        'P708' : 'wikibase-item', 'P71' : 'wikibase-item', 'P710' : 'wikibase-item', 'P711' : 'string',
        'P712' : 'string', 'P713' : 'string', 'P714' : 'string', 'P715' : 'string',
        'P716' : 'string', 'P717' : 'string', 'P720' : 'wikibase-item', 'P721' : 'string',
        'P722' : 'string', 'P723' : 'string', 'P727' : 'string', 'P728' : 'string',
        'P729' : 'time', 'P730' : 'time', 'P734' : 'wikibase-item', 'P735' : 'wikibase-item',
        'P739' : 'wikibase-item', 'P74' : 'wikibase-item', 'P740' : 'wikibase-item', 'P741' : 'wikibase-item',
        'P742' : 'string', 'P743' : 'string', 'P744' : 'wikibase-item', 'P747' : 'wikibase-item',
        'P748' : 'wikibase-item', 'P749' : 'wikibase-item', 'P75' : 'wikibase-item', 'P750' : 'wikibase-item',
        'P757' : 'string', 'P758' : 'string', 'P76' : 'wikibase-item', 'P765' : 'wikibase-item',
        'P766' : 'wikibase-item', 'P768' : 'wikibase-item', 'P77' : 'wikibase-item', 'P770' : 'wikibase-item',
        'P771' : 'string', 'P772' : 'string', 'P773' : 'string', 'P774' : 'string',
        'P775' : 'string', 'P78' : 'wikibase-item', 'P780' : 'wikibase-item', 'P782' : 'string',
        'P790' : 'wikibase-item', 'P791' : 'string', 'P792' : 'string', 'P793' : 'wikibase-item',
        'P794' : 'wikibase-item', 'P802' : 'wikibase-item', 'P804' : 'string', 'P805' : 'wikibase-item',
        'P806' : 'string', 'P807' : 'wikibase-item', 'P809' : 'string', 'P81' : 'wikibase-item',
        'P813' : 'time', 'P814' : 'wikibase-item', 'P815' : 'string', 'P816' : 'wikibase-item',
        'P817' : 'wikibase-item', 'P821' : 'string', 'P824' : 'string', 'P825' : 'wikibase-item',
        'P826' : 'wikibase-item', 'P827' : 'string', 'P828' : 'wikibase-item', 'P829' : 'string',
        'P830' : 'string', 'P832' : 'wikibase-item', 'P833' : 'wikibase-item', 'P835' : 'string',
        'P836' : 'string', 'P837' : 'wikibase-item', 'P838' : 'string', 'P839' : 'string',
        'P84' : 'wikibase-item', 'P840' : 'wikibase-item', 'P841' : 'wikibase-item', 'P842' : 'string',
        'P846' : 'string', 'P847' : 'string', 'P85' : 'wikibase-item', 'P852' : 'wikibase-item',
        'P853' : 'wikibase-item', 'P854' : 'url', 'P856' : 'url', 'P858' : 'string',
        'P86' : 'wikibase-item', 'P861' : 'string', 'P866' : 'string', 'P867' : 'string',
        'P87' : 'wikibase-item', 'P870' : 'wikibase-item', 'P872' : 'wikibase-item', 'P873' : 'wikibase-item',
        'P874' : 'string', 'P876' : 'string', 'P877' : 'string', 'P88' : 'wikibase-item',
        'P880' : 'wikibase-item', 'P884' : 'string', 'P89' : 'wikibase-item', 'P897' : 'string',
        'P898' : 'string', 'P9' : 'wikibase-item', 'P901' : 'string', 'P905' : 'string',
        'P906' : 'string', 'P907' : 'string', 'P908' : 'wikibase-item', 'P91' : 'wikibase-item',
        'P910' : 'wikibase-item', 'P913' : 'wikibase-item', 'P914' : 'wikibase-item', 'P92' : 'wikibase-item',
        'P920' : 'string', 'P921' : 'wikibase-item', 'P923' : 'wikibase-item', 'P924' : 'wikibase-item',
        'P931' : 'wikibase-item', 'P935' : 'string', 'P937' : 'wikibase-item', 'P939' : 'string',
        'P94' : 'commonsMedia', 'P940' : 'string', 'P942' : 'wikibase-item', 'P944' : 'wikibase-item',
        'P945' : 'wikibase-item', 'P947' : 'string', 'P948' : 'commonsMedia', 'P949' : 'string',
        'P950' : 'string', 'P951' : 'string', 'P954' : 'string', 'P957' : 'string',
        'P958' : 'string', 'P961' : 'string', 'P963' : 'url', 'P964' : 'string',
        'P965' : 'string', 'P966' : 'string', 'P97' : 'wikibase-item', 'P971' : 'wikibase-item',
        'P972' : 'wikibase-item', 'P973' : 'url', 'P98' : 'wikibase-item', 'P982' : 'string',
        'P984' : 'string', 'P990' : 'commonsMedia', 'P991' : 'wikibase-item', 'P992' : 'wikibase-item',
        'P993' : 'string', 'P994' : 'string', 'P995' : 'string', 'P998' : 'string'
}
