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
		self.entityCount = 0
		self.propertyCount = 0
		self.propertyLookupCount = 0
		self.propertyTypes = {}
		self.propertyDeclarationQueue = []
		self.filterName = self.dataFilter.getHashCode()

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
		self.output.write( "\nwo:propertyType\ta\to:ObjectProperty ." )
		self.output.write( "\nwo:globe\ta\to:ObjectProperty ." )
		self.output.write( "\nwo:latitude\ta\to:DatatypeProperty ." )
		self.output.write( "\nwo:longitude\ta\to:DatatypeProperty ." )
		self.output.write( "\nwo:altitude\ta\to:DatatypeProperty ." )
		self.output.write( "\nwo:gcPrecision\ta\to:DatatypeProperty ." )
		self.output.write( "\nwo:time\ta\to:DatatypeProperty ." )
		self.output.write( "\nwo:timePrecision\ta\to:DatatypeProperty ." )
		#self.output.write( "\nwo:timePrecisionAfter\ta\to:DatatypeProperty ." ) # currently unused
		#self.output.write( "\nwo:timePrecisionBefore\ta\to:DatatypeProperty ." ) # currently unused
		self.output.write( "\nwo:preferredCalendar\ta\to:ObjectProperty ." )
		# Other external properties that have a clear declaration:
		# (we omit the rdfs and skos properties, which lack a clear typing)
		self.output.write( "\npv:wasDerivedFrom\ta\to:ObjectProperty ." )
		self.output.write( "\nso:about\ta\to:ObjectProperty ." )
		self.output.write( "\nso:inLanguage\ta\to:DatatypeProperty ." )
		self.output.write("\n")

	def processEntity(self,title,revision,isItem,data):
		self.entityCount += 1
		self.refs = {} # collect references to export duplicates only once per item

		if isItem:
			self.output.write( '\nw:' + title + "\n\ta\two:Item" )
		else:
			self.output.write( '\nw:' + title + "\n\ta\two:Property" )

		# Write datatype information, if any
		if 'datatype' in data:
			self.__setPropertyType(title,data['datatype'],True)
			if data['datatype'] == 'wikibase-item':
				self.output.write( " ;\n\two:propertyType\two:propertyTypeItem" )
			elif data['datatype'] == 'string':
				self.output.write( " ;\n\two:propertyType\two:propertyTypeString" )
			elif data['datatype'] == 'commonsMedia':
				self.output.write( " ;\n\two:propertyType\two:propertyTypeCommonsMedia" )
			elif data['datatype'] == 'time':
				self.output.write( " ;\n\two:propertyType\two:propertyTypeTime" )
			elif data['datatype'] == 'globe-coordinate':
				self.output.write( " ;\n\two:propertyType\two:propertyTypeGlobeCoordinates")
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
					self.output.write( ",w:" + statement['localname'])
				else:
					curProperty = statement['m'][1]
					self.output.write( " ;\n\tw:P" + str(curProperty) + "s\tw:" + statement['localname'])

		self.output.write(" .\n")

		# Export statements:
		if self.dataFilter.includeStatements():
			for statement in statements:
				self.__writeStatementData(statement)

		# Export collected references:
		if self.dataFilter.includeReferences():
			for key in self.refs.keys():
				self.output.write( '\nw:' + key + "\n\ta\two:Reference" )
				for snak in self.refs[key]:
					self.__writeSnakData("w:P" + str(snak[1]) + 'r', snak)
				self.output.write(" .\n")

		# Export links:
		for sitekey in data['links'].keys() :
			if not self.dataFilter.includeSite(sitekey):
				continue
			if sitekey[-10:] == 'wikivoyage':
				urlPrefix = 'http://' + sitekey[:-10].replace('_','-') + '.wikivoyage.org/wiki/'
			elif sitekey[-4:] == 'wiki':
				urlPrefix = 'http://' + sitekey[:-4].replace('_','-') + '.wikipedia.org/wiki/'
			else:
				logging.log("*** Warning: the following sitekey was not understood: " + sitekey)
				continue

			articletitle = data['links'][sitekey].encode('utf-8')
			self.output.write( "\n<" + urlPrefix + urllib.quote(articletitle) + ">\n\ta\tso:Article" )
			self.output.write( " ;\n\tso:about\tw:" + title )
			if sitekey in siteLanguageCodes:
				self.output.write( " ;\n\tso:inLanguage\t\"" + siteLanguageCodes[sitekey] + "\"")
			else:
				logging.log( '*** Warning: Language code unknown for site "' + sitekey + '".'  )
			self.output.write(" .\n")

		self.__writePropertyDeclarations()

	def logReport(self):
		## Dump collected types to update the cache at the end of this file (normally done only at the very end):
		#self.__knownTypesReport()
		logging.log('     * Turtle serialization (' + self.filterName + '): ' + str(self.entityCount) + ' entities, definitions for ' + str(self.propertyCount) + ' properties (looked up ' + str(self.propertyLookupCount) + ' types online).')

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

	def close(self):
		self.output.write("\n\n ### Export completed successfully. The End. ###")
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

		lowTitle = 'p' + propertyTitle[1:]
		logging.logMore('Fetching current datatype of property ' + propertyTitle + ' from wikidata.org ... ' )
		self.propertyLookupCount += 1
		for line in urllib.urlopen('http://www.wikidata.org/w/api.php?action=wbgetentities&ids=' + lowTitle + '&props=datatype&format=json'):
			data = eval(line)
			if 'entities' in data and lowTitle in data['entities'] and 'datatype' in data['entities'][lowTitle]:
				logging.log('found type ' + data['entities'][lowTitle]['datatype'])
				knownPropertyTypes[propertyTitle] = data['entities'][lowTitle]['datatype'] # share with all instances of this class
				return data['entities'][lowTitle]['datatype']

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
			self.output.write( '\nw:' + propertyTitle + "s\ta\to:ObjectProperty ." )
			if self.__getPropertyRange(propertyTitle) == 'o:Thing':
				self.output.write( '\nw:' + propertyTitle + "v\ta\to:ObjectProperty ." )
				self.output.write( '\nw:' + propertyTitle + "r\ta\to:ObjectProperty ." )
				self.output.write( '\nw:' + propertyTitle + "q\ta\to:ObjectProperty ." )
			else:
				self.output.write( '\nw:' + propertyTitle + "v\ta\to:DatatypeProperty ." )
				self.output.write( '\nw:' + propertyTitle + "r\ta\to:DatatypeProperty ." )
				self.output.write( '\nw:' + propertyTitle + "q\ta\to:DatatypeProperty ." )
			self.output.write( '\n' )
			self.propertyCount += 1

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

		try:
			yearnum = int(wikidataTime[:12])
			month = wikidataTime[13:15]
			day = wikidataTime[16:18]
		except ValueError: # some rare values seem to have other year lengths
			logging.log("*** Warning: unexpected date format '" + wikidataTime + "'.")
			return '"' + wikidataTime + '"^^x:dateTime' # let's hope this works

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
			if valueList and literals[lang] == []: # deal with https://bugzilla.wikimedia.org/show_bug.cgi?id=44717
				continue
			if first:
				self.output.write( " ;\n\t" + prop + "\t")
				first = False
			else:
				self.output.write(',')

			if valueList:
				firstLiteral = True
				for literal in literals[lang]:
					if firstLiteral:
						firstLiteral = False
					else:
						self.output.write(',')
					self.output.write( self.__encodeStringLiteral(literal, lang) )
			else:
				self.output.write( self.__encodeStringLiteral(literals[lang], lang) )

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
		self.valuesGC = {} # collect coordinates values and export them after each statement
		self.valuesTI = {} # collect time values and export them after each statement

		self.output.write( '\nw:' + statement['localname'] + "\n\ta\two:Statement" )
		self.__writeSnakData("w:P" + str(statement['m'][1]) + 'v', statement['m'])
		for q in statement['q']:
			self.__writeSnakData("w:P" + str(q[1]) + 'q', q)

		if self.dataFilter.includeReferences():
			for ref in statement['refs']:
				key = "R" + self.__getHashForLocalName(ref)
				self.refs[key] = ref
				self.output.write( " ;\n\tpv:wasDerivedFrom\tw:" + key )

		self.output.write(" .\n")

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
		self.output.write( '\nw:' + localname + "\n\ta\two:TimeValue" )
		self.output.write( " ;\n\two:time\t" + self.__encodeTimeLiteral(value['time'],value['precision']) )
		self.output.write( " ;\n\two:timePrecision\t" + self.__encodeIntegerLiteral(value['precision']) )
		## TODO Currently unused -- do not export yet.
		#self.output.write( " ;\n\two:timePrecisionBefore\t" + self.__encodeIntegerLiteral(value['before']) )
		#self.output.write( " ;\n\two:timePrecisionAfter\t" + self.__encodeIntegerLiteral(value['after']) )
		self.output.write( " ;\n\two:preferredCalendar\tw:" + value['calendarmodel'][35:] )
		self.output.write(" .\n")

	# Write the data for a coordinates datavalue with the given local name.
	def __writeCoordinatesValue(self,localname,value):
		self.output.write( '\nw:' + localname + "\n\ta\two:GlobeCoordinatesValue" )
		self.output.write( " ;\n\two:latitude\t" + self.__encodeFloatLiteral(value['latitude']) )
		self.output.write( " ;\n\two:longitude\t" + self.__encodeFloatLiteral(value['longitude']) )
		if value['altitude'] != None:
			self.output.write( " ;\n\two:altitude\t" + self.__encodeFloatLiteral(value['altitude']) )
		if value['precision'] != None:
			self.output.write( " ;\n\two:gcPrecision\t" + self.__encodeFloatLiteral(value['precision']) )
		if value['globe'] != None:
			self.output.write( " ;\n\two:globe\tw:" + value['globe'][31:] )
		self.output.write(" .\n")

	# Write the data for one snak. Since we use different variants of
	# property URIs depending on context, the property URI is explicitly
	# given rather than being derived from the snak.
	def __writeSnakData(self,prop,snak):
		includeSnak = True
		wbProperty = 'P' + str(snak[1]) # Not to be confused with prop
		if snak[0] == 'value' :
			if snak[2] in datatypesByValueTypes:
				datatype = self.__setPropertyType(wbProperty, datatypesByValueTypes[snak[2]])
			else:
				datatype = None

			if self.dataFilter.includePropertyType(datatype):
				if datatype == 'wikibase-item':
					self.output.write( " ;\n\t" + prop + "\tw:Q" + str(snak[3]['numeric-id']) )
				elif datatype == 'commonsMedia':
					self.output.write( " ;\n\t" + prop + "\t<http://commons.wikimedia.org/wiki/File:" +  urllib.quote(snak[3].replace(' ','_').encode('utf-8')) + '>' )
				elif datatype == 'string':
					self.output.write( " ;\n\t" + prop + "\t" + self.__encodeStringLiteral(snak[3]) )
				elif datatype == 'time' :
					key = 'VT' + self.__getHashForLocalName(snak[3])
					self.valuesTI[key] = snak[3]
					self.output.write( " ;\n\t" + prop + "\tw:" + key )
				elif datatype == 'globe-coordinate' :
					key = 'VC' + self.__getHashForLocalName(snak[3])
					self.valuesGC[key] = snak[3]
					self.output.write( " ;\n\t" + prop + "\tw:" + key )
				else :
					logging.log('*** Warning: Unsupported value snak:\n' + str(snak) + '\nExport might be incomplete.\n')
					includeSnak = False
			else:
				includeSnak = False
		elif snak[0] == 'somevalue' :
			datatype = self.__getPropertyType(wbProperty)
			if self.dataFilter.includePropertyType(datatype):
				propRange = self.__getPropertyRange(wbProperty)
				self.output.write( " ;\n\ta\t[ a o:Restriction; o:onProperty " + prop + "; o:someValuesFrom " + propRange + " ]" )
			else:
				includeSnak = False
		elif snak[0] == 'novalue' :
			datatype = self.__getPropertyType(wbProperty)
			if self.dataFilter.includePropertyType(datatype):
				propRange = self.__getPropertyRange(wbProperty)
				if propRange == 'o:Thing':
					self.output.write( " ;\n\ta\t[ a o:Class; o:complementOf [ a o:Restriction; o:onProperty " + prop + "; o:someValuesFrom o:Thing ] ]" )
					#self.output.write( " ;\n\ta\t[ a o:Restriction; o:onProperty " + prop + "; o:allValuesFrom o:Nothing ]" ) # < shorter, but less uniform compared to data case
				else:
					self.output.write( " ;\n\ta\t[ a o:Class; o:complementOf [ a o:Restriction; o:onProperty " + prop + "; o:someValuesFrom rs:Literal ] ]" )
			else:
				includeSnak = False
		else :
			logging.log('*** Warning: Unsupported snak:\n' + str(snak) + '\nExport might be incomplete.\n')
			includeSnak = False

		if not includeSnak:
			self.output.write( " ;\n\ta\two:IncompletelyExported" )

	def __getHashForLocalName(self, obj):
		return '{0:x}'.format(abs(hash(str(obj))))

# Wikidata datatypes for which the OWL value property
# is an ObjectProperty (rather than a DatatypeProperty).
owlPropertyRanges = {
	'wikibase-item': 'o:Thing',
	'string': 'x:string',
	'time': 'o:Thing',
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
# So far, this is mostly identity; needs careful revision.
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
	'P10' : 'commonsMedia', 'P100' : 'wikibase-item', 'P101' : 'wikibase-item', 'P102' : 'wikibase-item',
	'P103' : 'wikibase-item', 'P105' : 'wikibase-item', 'P106' : 'wikibase-item', 'P107' : 'wikibase-item',
	'P108' : 'wikibase-item', 'P109' : 'commonsMedia', 'P110' : 'wikibase-item', 'P111' : 'wikibase-item',
	'P112' : 'wikibase-item', 'P113' : 'wikibase-item', 'P114' : 'wikibase-item', 'P115' : 'wikibase-item',
	'P117' : 'commonsMedia', 'P118' : 'wikibase-item', 'P119' : 'wikibase-item', 'P121' : 'wikibase-item',
	'P122' : 'wikibase-item', 'P123' : 'wikibase-item', 'P126' : 'wikibase-item', 'P127' : 'wikibase-item',
	'P128' : 'wikibase-item', 'P129' : 'wikibase-item', 'P131' : 'wikibase-item', 'P132' : 'wikibase-item',
	'P133' : 'wikibase-item', 'P134' : 'wikibase-item', 'P135' : 'wikibase-item', 'P136' : 'wikibase-item',
	'P137' : 'wikibase-item', 'P138' : 'wikibase-item', 'P14' : 'commonsMedia', 'P140' : 'wikibase-item',
	'P141' : 'wikibase-item', 'P143' : 'wikibase-item', 'P144' : 'wikibase-item', 'P149' : 'wikibase-item',
	'P15' : 'commonsMedia', 'P150' : 'wikibase-item', 'P154' : 'commonsMedia', 'P155' : 'wikibase-item',
	'P156' : 'wikibase-item', 'P157' : 'wikibase-item', 'P158' : 'commonsMedia', 'P159' : 'wikibase-item',
	'P16' : 'wikibase-item', 'P160' : 'wikibase-item', 'P161' : 'wikibase-item', 'P162' : 'wikibase-item',
	'P163' : 'wikibase-item', 'P164' : 'wikibase-item', 'P166' : 'wikibase-item', 'P167' : 'wikibase-item',
	'P168' : 'wikibase-item', 'P169' : 'wikibase-item', 'P17' : 'wikibase-item', 'P170' : 'wikibase-item',
	'P171' : 'wikibase-item', 'P172' : 'wikibase-item', 'P173' : 'wikibase-item', 'P175' : 'wikibase-item',
	'P176' : 'wikibase-item', 'P177' : 'wikibase-item', 'P178' : 'wikibase-item', 'P179' : 'wikibase-item',
	'P18' : 'commonsMedia', 'P180' : 'wikibase-item', 'P181' : 'commonsMedia', 'P183' : 'wikibase-item',
	'P184' : 'wikibase-item', 'P185' : 'wikibase-item', 'P186' : 'wikibase-item', 'P189' : 'wikibase-item',
	'P19' : 'wikibase-item', 'P190' : 'wikibase-item', 'P193' : 'wikibase-item', 'P194' : 'wikibase-item',
	'P195' : 'wikibase-item', 'P196' : 'wikibase-item', 'P197' : 'wikibase-item', 'P198' : 'wikibase-item',
	'P199' : 'wikibase-item', 'P20' : 'wikibase-item', 'P200' : 'wikibase-item', 'P201' : 'wikibase-item',
	'P202' : 'wikibase-item', 'P205' : 'wikibase-item', 'P206' : 'wikibase-item', 'P207' : 'commonsMedia',
	'P208' : 'wikibase-item', 'P209' : 'wikibase-item', 'P21' : 'wikibase-item', 'P210' : 'wikibase-item',
	'P212' : 'string', 'P213' : 'string', 'P214' : 'string', 'P215' : 'string',
	'P217' : 'string', 'P218' : 'string', 'P219' : 'string', 'P22' : 'wikibase-item',
	'P220' : 'string', 'P221' : 'string', 'P223' : 'string', 'P225' : 'string',
	'P227' : 'string', 'P229' : 'string', 'P230' : 'string', 'P231' : 'string',
	'P232' : 'string', 'P233' : 'string', 'P234' : 'string', 'P235' : 'string',
	'P236' : 'string', 'P237' : 'wikibase-item', 'P238' : 'string', 'P239' : 'string',
	'P240' : 'string', 'P241' : 'wikibase-item', 'P242' : 'commonsMedia', 'P243' : 'string',
	'P244' : 'string', 'P245' : 'string', 'P246' : 'string', 'P247' : 'string',
	'P248' : 'wikibase-item', 'P249' : 'string', 'P25' : 'wikibase-item', 'P26' : 'wikibase-item',
	'P263' : 'wikibase-item', 'P264' : 'wikibase-item', 'P267' : 'string', 'P268' : 'string',
	'P269' : 'string', 'P27' : 'wikibase-item', 'P270' : 'string', 'P271' : 'string',
	'P272' : 'wikibase-item', 'P273' : 'wikibase-item', 'P274' : 'string', 'P275' : 'wikibase-item',
	'P276' : 'wikibase-item', 'P277' : 'wikibase-item', 'P278' : 'string', 'P279' : 'wikibase-item',
	'P281' : 'string', 'P282' : 'wikibase-item', 'P283' : 'wikibase-item', 'P284' : 'wikibase-item',
	'P285' : 'wikibase-item', 'P286' : 'wikibase-item', 'P287' : 'wikibase-item', 'P288' : 'wikibase-item',
	'P289' : 'wikibase-item', 'P291' : 'wikibase-item', 'P295' : 'wikibase-item', 'P296' : 'string',
	'P297' : 'string', 'P298' : 'string', 'P299' : 'string', 'P30' : 'wikibase-item',
	'P300' : 'string', 'P301' : 'wikibase-item', 'P302' : 'wikibase-item', 'P303' : 'string',
	'P304' : 'string', 'P305' : 'string', 'P306' : 'wikibase-item', 'P31' : 'wikibase-item',
	'P344' : 'wikibase-item', 'P345' : 'string', 'P347' : 'string', 'P348' : 'string',
	'P349' : 'string', 'P35' : 'wikibase-item', 'P350' : 'string', 'P351' : 'string',
	'P352' : 'string', 'P353' : 'string', 'P354' : 'string', 'P355' : 'wikibase-item',
	'P356' : 'string', 'P357' : 'string', 'P358' : 'wikibase-item', 'P359' : 'string',
	'P36' : 'wikibase-item', 'P360' : 'wikibase-item', 'P361' : 'wikibase-item', 'P364' : 'wikibase-item',
	'P366' : 'wikibase-item', 'P367' : 'commonsMedia', 'P368' : 'commonsMedia', 'P369' : 'wikibase-item',
	'P37' : 'wikibase-item', 'P370' : 'string', 'P371' : 'wikibase-item', 'P373' : 'string',
	'P374' : 'string', 'P375' : 'wikibase-item', 'P376' : 'wikibase-item', 'P377' : 'string',
	'P38' : 'wikibase-item', 'P380' : 'string', 'P381' : 'string', 'P382' : 'string',
	'P387' : 'string', 'P39' : 'wikibase-item', 'P392' : 'string', 'P393' : 'string',
	'P395' : 'string', 'P396' : 'string', 'P397' : 'wikibase-item', 'P398' : 'wikibase-item',
	'P399' : 'wikibase-item', 'P40' : 'wikibase-item', 'P400' : 'wikibase-item', 'P402' : 'string',
	'P403' : 'wikibase-item', 'P404' : 'wikibase-item', 'P405' : 'wikibase-item', 'P406' : 'wikibase-item',
	'P407' : 'wikibase-item', 'P408' : 'wikibase-item', 'P409' : 'string', 'P41' : 'commonsMedia',
	'P410' : 'wikibase-item', 'P411' : 'wikibase-item', 'P412' : 'wikibase-item', 'P413' : 'wikibase-item',
	'P414' : 'wikibase-item', 'P415' : 'wikibase-item', 'P416' : 'string', 'P417' : 'wikibase-item',
	'P418' : 'wikibase-item', 'P421' : 'wikibase-item', 'P423' : 'wikibase-item', 'P424' : 'string',
	'P425' : 'wikibase-item', 'P426' : 'string', 'P427' : 'wikibase-item', 'P428' : 'string',
	'P429' : 'string', 'P43' : 'wikibase-item', 'P432' : 'string', 'P433' : 'string',
	'P434' : 'string', 'P435' : 'string', 'P436' : 'string', 'P437' : 'wikibase-item',
	'P438' : 'string', 'P439' : 'string', 'P44' : 'wikibase-item', 'P440' : 'string',
	'P442' : 'string', 'P443' : 'commonsMedia', 'P444' : 'string', 'P447' : 'wikibase-item',
	'P448' : 'wikibase-item', 'P449' : 'wikibase-item', 'P45' : 'wikibase-item', 'P450' : 'wikibase-item',
	'P451' : 'wikibase-item', 'P452' : 'wikibase-item', 'P453' : 'wikibase-item', 'P454' : 'string',
	'P455' : 'string', 'P457' : 'wikibase-item', 'P458' : 'string', 'P459' : 'wikibase-item',
	'P460' : 'wikibase-item', 'P461' : 'wikibase-item', 'P462' : 'wikibase-item', 'P463' : 'wikibase-item',
	'P464' : 'string', 'P465' : 'string', 'P466' : 'wikibase-item', 'P467' : 'wikibase-item',
	'P468' : 'wikibase-item', 'P469' : 'wikibase-item', 'P47' : 'wikibase-item', 'P470' : 'wikibase-item',
	'P473' : 'string', 'P474' : 'string', 'P476' : 'string', 'P477' : 'string',
	'P478' : 'string', 'P479' : 'wikibase-item', 'P480' : 'string', 'P481' : 'string',
	'P483' : 'wikibase-item', 'P484' : 'string', 'P485' : 'wikibase-item', 'P486' : 'string',
	'P487' : 'string', 'P488' : 'wikibase-item', 'P489' : 'wikibase-item', 'P490' : 'string',
	'P491' : 'commonsMedia', 'P492' : 'string', 'P493' : 'string', 'P494' : 'string',
	'P495' : 'wikibase-item', 'P496' : 'string', 'P497' : 'string', 'P498' : 'string',
	'P50' : 'wikibase-item', 'P500' : 'wikibase-item', 'P501' : 'wikibase-item', 'P502' : 'string',
	'P503' : 'string', 'P504' : 'wikibase-item', 'P505' : 'wikibase-item', 'P506' : 'string',
	'P507' : 'string', 'P508' : 'string', 'P509' : 'wikibase-item', 'P51' : 'commonsMedia',
	'P511' : 'wikibase-item', 'P512' : 'wikibase-item', 'P513' : 'string', 'P514' : 'wikibase-item',
	'P515' : 'wikibase-item', 'P516' : 'wikibase-item', 'P517' : 'wikibase-item', 'P518' : 'wikibase-item',
	'P520' : 'wikibase-item', 'P521' : 'wikibase-item', 'P522' : 'wikibase-item', 'P523' : 'wikibase-item',
	'P524' : 'wikibase-item', 'P525' : 'string', 'P527' : 'wikibase-item', 'P528' : 'string',
	'P529' : 'string', 'P53' : 'wikibase-item', 'P530' : 'wikibase-item', 'P531' : 'wikibase-item',
	'P532' : 'wikibase-item', 'P533' : 'wikibase-item', 'P534' : 'wikibase-item', 'P535' : 'string',
	'P536' : 'string', 'P537' : 'wikibase-item', 'P538' : 'wikibase-item', 'P539' : 'string',
	'P54' : 'wikibase-item', 'P540' : 'wikibase-item', 'P541' : 'wikibase-item', 'P542' : 'wikibase-item',
	'P543' : 'wikibase-item', 'P545' : 'wikibase-item', 'P546' : 'wikibase-item', 'P547' : 'wikibase-item',
	'P548' : 'wikibase-item', 'P549' : 'string', 'P550' : 'wikibase-item', 'P551' : 'wikibase-item',
	'P552' : 'wikibase-item', 'P553' : 'wikibase-item', 'P554' : 'string', 'P555' : 'string',
	'P556' : 'wikibase-item', 'P557' : 'string', 'P558' : 'string', 'P559' : 'wikibase-item',
	'P560' : 'wikibase-item', 'P561' : 'string', 'P562' : 'wikibase-item', 'P563' : 'string',
	'P564' : 'string', 'P565' : 'wikibase-item', 'P566' : 'wikibase-item', 'P567' : 'wikibase-item',
	'P568' : 'wikibase-item', 'P569' : 'time', 'P57' : 'wikibase-item', 'P570' : 'time',
	'P571' : 'time', 'P574' : 'time', 'P575' : 'time', 'P576' : 'time',
	'P577' : 'time', 'P578' : 'time', 'P579' : 'wikibase-item', 'P58' : 'wikibase-item',
	'P580' : 'time', 'P582' : 'time', 'P585' : 'time', 'P586' : 'string',
	'P587' : 'string', 'P588' : 'wikibase-item', 'P589' : 'wikibase-item', 'P59' : 'wikibase-item',
	'P590' : 'string', 'P591' : 'string', 'P592' : 'string', 'P593' : 'string',
	'P594' : 'string', 'P595' : 'string', 'P597' : 'string', 'P598' : 'wikibase-item',
	'P599' : 'string', 'P6' : 'wikibase-item', 'P60' : 'wikibase-item', 'P600' : 'string',
	'P604' : 'string', 'P605' : 'string', 'P606' : 'time', 'P607' : 'wikibase-item',
	'P608' : 'wikibase-item', 'P609' : 'wikibase-item', 'P61' : 'wikibase-item', 'P610' : 'wikibase-item',
	'P611' : 'wikibase-item', 'P612' : 'wikibase-item', 'P613' : 'string', 'P616' : 'string',
	'P617' : 'string', 'P618' : 'wikibase-item', 'P619' : 'time', 'P620' : 'time',
	'P621' : 'time', 'P622' : 'time', 'P623' : 'commonsMedia', 'P624' : 'wikibase-item',
	'P625' : 'globe-coordinate', 'P626' : 'globe-coordinate', 'P627' : 'string', 'P628' : 'string',
	'P629' : 'wikibase-item', 'P630' : 'string', 'P631' : 'wikibase-item', 'P632' : 'string',
	'P633' : 'string', 'P634' : 'wikibase-item', 'P635' : 'string', 'P636' : 'wikibase-item',
	'P637' : 'string', 'P638' : 'string', 'P639' : 'string', 'P640' : 'string',
	'P641' : 'wikibase-item', 'P642' : 'wikibase-item', 'P643' : 'string', 'P644' : 'string',
	'P645' : 'string', 'P646' : 'string', 'P647' : 'wikibase-item', 'P648' : 'string',
	'P649' : 'string', 'P65' : 'wikibase-item', 'P650' : 'string', 'P651' : 'string',
	'P652' : 'string', 'P653' : 'string', 'P654' : 'wikibase-item', 'P655' : 'wikibase-item',
	'P656' : 'string', 'P657' : 'string', 'P658' : 'wikibase-item', 'P659' : 'wikibase-item',
	'P66' : 'wikibase-item', 'P660' : 'wikibase-item', 'P661' : 'string', 'P662' : 'string',
	'P663' : 'string', 'P664' : 'wikibase-item', 'P665' : 'string', 'P667' : 'string',
	'P668' : 'string', 'P669' : 'wikibase-item', 'P670' : 'string', 'P671' : 'string',
	'P672' : 'string', 'P673' : 'string', 'P674' : 'wikibase-item', 'P675' : 'string',
	'P676' : 'wikibase-item', 'P677' : 'string', 'P678' : 'wikibase-item', 'P679' : 'string',
	'P680' : 'wikibase-item', 'P681' : 'wikibase-item', 'P682' : 'wikibase-item', 'P683' : 'string',
	'P684' : 'wikibase-item', 'P685' : 'string', 'P686' : 'string', 'P687' : 'string',
	'P688' : 'wikibase-item', 'P689' : 'wikibase-item', 'P69' : 'wikibase-item', 'P690' : 'wikibase-item',
	'P691' : 'string', 'P692' : 'commonsMedia', 'P693' : 'wikibase-item', 'P694' : 'wikibase-item',
	'P695' : 'string', 'P696' : 'string', 'P697' : 'wikibase-item', 'P698' : 'string',
	'P699' : 'string', 'P7' : 'wikibase-item', 'P70' : 'wikibase-item', 'P700' : 'string',
	'P701' : 'string', 'P702' : 'wikibase-item', 'P703' : 'wikibase-item', 'P704' : 'string',
	'P705' : 'string', 'P706' : 'wikibase-item', 'P707' : 'wikibase-item', 'P708' : 'wikibase-item',
	'P709' : 'string', 'P71' : 'wikibase-item', 'P710' : 'wikibase-item', 'P711' : 'string',
	'P712' : 'string', 'P713' : 'string', 'P714' : 'string', 'P715' : 'string',
	'P716' : 'string', 'P717' : 'string', 'P718' : 'string', 'P719' : 'wikibase-item',
	'P720' : 'wikibase-item', 'P721' : 'string', 'P722' : 'string', 'P723' : 'string',
	'P724' : 'string', 'P725' : 'wikibase-item', 'P726' : 'wikibase-item', 'P727' : 'string',
	'P728' : 'string', 'P729' : 'time', 'P730' : 'time', 'P731' : 'string',
	'P732' : 'string', 'P733' : 'string', 'P734' : 'wikibase-item', 'P735' : 'wikibase-item',
	'P74' : 'wikibase-item', 'P75' : 'wikibase-item', 'P76' : 'wikibase-item', 'P77' : 'wikibase-item',
	'P78' : 'wikibase-item', 'P81' : 'wikibase-item', 'P84' : 'wikibase-item', 'P85' : 'wikibase-item',
	'P86' : 'wikibase-item', 'P87' : 'wikibase-item', 'P88' : 'wikibase-item', 'P89' : 'wikibase-item',
	'P9' : 'wikibase-item', 'P91' : 'wikibase-item', 'P92' : 'wikibase-item', 'P94' : 'commonsMedia',
	'P97' : 'wikibase-item', 'P98' : 'wikibase-item'
}

