#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import entityprocessor

# Entity processor that writes entity data to a file using
# a compact syntactic format.
class EPKbFile(entityprocessor.EntityProcessor):

	def __init__(self,outputFile):
		self.output = outputFile
		self.entityCount = 0

	def processEntity(self,title,revision,isItem,data):
		self.entityCount += 1

		if 'datatype' in data:
			self.output.write(title + ' type ' + data['datatype'] + " .\n")

		if 'label' in data and len(data['label']) > 0 :
			for lang in data['label'].keys() :
				self.output.write(title + ' label {' + lang + ':' + data['label'][lang] + "} .\n")

		if 'description' in data and len(data['description']) > 0 :
			for lang in data['description'].keys() :
				self.output.write(title + ' description {' + lang + ':' + data['description'][lang] + "} .\n")

		if 'links' in data and len(data['links']) > 0 :
			for lang in data['links'].keys() :
				self.output.write(title + ' link {' + lang + ':' + data['links'][lang] + "} .\n")

		if 'aliases' in data and len(data['aliases']) > 0 :
			for lang in data['aliases'].keys() :
				for alias in data['aliases'][lang] :
					self.output.write(title + ' alias {' + lang + ':' + alias + "} .\n")

		if 'claims' in data and len(data['claims']) > 0 :
			for claim in data['claims'] :
				quals = ''
				if (len(claim['q']) + len(claim['refs'])) > 0 :
					if (len(claim['q']) > 0) :
						for q in claim['q'] :
							quals += '  ' + self.__snakToText(q) + " ,\n"
					if (len(claim['refs']) > 0) :
						for ref in claim['refs'] :
							quals += "  reference {\n"
							for r in ref :
								quals += '    ' + self.__snakToText(r) + " ,\n"
							quals += "  },\n"
					quals = " (\n" + quals + ' )'

				snak = self.__snakToText(claim['m'])
				self.output.write(title + ' ' + snak + quals + " .\n")

	def logReport(self):
		logging.log('     * Serialized ' + str(self.entityCount) + ' entities using the KB format.')

	def close(self):
		#self.output.write("\n\n ### Export completed successfully. The End. ###")
		self.output.close()

	def __snakToText(self,snak) :
		if snak[0] == 'value' :
			if snak[2] == 'wikibase-entityid' :
				return 'P' + str(snak[1]) + ' Q' + str(snak[3]['numeric-id'])
			elif snak[2] == 'string' :
				return 'P' + str(snak[1]) + ' {' + snak[3] + '}'
			elif snak[2] == 'time' :
				return 'P' + str(snak[1]) + ' ' + str(snak[3])
			elif snak[2] == 'globecoordinate' :
				return 'P' + str(snak[1]) + ' ' + str(snak[3])
			else :
				print snak
				exit()
		elif snak[0] == 'somevalue' :
			return 'P' + str(snak[1]) + ' +'
		elif snak[0] == 'novalue' :
			return 'P' + str(snak[1]) + ' -'
		else :
			print snak
			exit()
