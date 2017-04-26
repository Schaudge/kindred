
import sys

from sklearn import svm
import numpy as np
from collections import defaultdict

from sklearn.feature_selection import SelectKBest,chi2,SelectPercentile,RFECV
from sklearn.metrics import f1_score,confusion_matrix
from sklearn.ensemble import AdaBoostClassifier,GradientBoostingClassifier,BaggingClassifier,RandomForestClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression

from sklearn.model_selection import cross_val_score,cross_val_predict,StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC,SVC

from scipy.sparse import coo_matrix, csr_matrix, lil_matrix, hstack, vstack
from sklearn.linear_model import LogisticRegression

import kindred
from kindred.CandidateBuilder import CandidateBuilder
from kindred.Vectorizer import Vectorizer

class Classifier_With_Threshold:
	def __init__(self,threshold=0.5):
		#self.clf = svm.SVC(kernel='linear', class_weight='balanced', probability=True)
		self.clf = LogisticRegression(class_weight='balanced')
		self.threshold = threshold

	def fit(self,X,Y):
		self.clf.fit(X,Y)
		self.classes_ = self.clf.classes_

	def predictSimple(self,X,Y):
		return self.clf.predict(X)
	def predict_proba(self,X):
		return self.clf.predict_proba(X)
		
	def predict(self,X):
		probs = self.clf.predict_proba(X)

		# Ignore probabilities that fall below our threshold
		probs[probs<self.threshold] = -1.0

		# But make sure that the negative class (class=0) always has a slightly higher value
		probs[:,0][probs[:,0]<self.threshold] = -0.5

		# And get the highest probability for each row
		predictions = np.argmax(probs,axis=1)

		return predictions
		
		


def save_sparse_csr(filename,array):
	np.savez(filename,data = array.data ,indices=array.indices,indptr =array.indptr, shape=array.shape )

def load_sparse_csr(filename):
	loader = np.load(filename)
	return csr_matrix((  loader['data'], loader['indices'], loader['indptr']),shape = loader['shape'])

def saveClasses(filename,classes):
	with open(filename,'w') as f:
		for c in classes:
			f.write("1\n" if c == True else "0\n")

class RelationClassifier:
	"""
	This is a class. Fantastic!
	"""
	def __init__(self,useSingleClassifier=True,useBuilder=False,tfidf=True,features=None,threshold=None):
		"""
		Constructor-time
		"""
		self.isTrained = False
		self.useSingleClassifier = useSingleClassifier
		self.useBuilder = useBuilder
		self.tfidf = tfidf

		self.defaultFeatures = ["selectedTokenTypes","ngrams_betweenEntities","bigrams","dependencyPathElements","dependencyPathNearSelected"]
		if not features is None:
			assert isinstance(features,list)
			self.defaultFeatures = features
			
		self.threshold = threshold
		#self.defaultFeatures = ["selectedTokenTypes","dependencyPathElements"]

	def buildFeatureSet(self,candidateRelations,classes,tfidf):
		vectorizers = {}
		trainVectors = {}

		featureChoice = ["selectedTokenTypes","dependencyPathElements","ngrams_betweenEntities","bigrams_betweenEntities","bigramsOfDependencyPath"]
		for feature in featureChoice:
			vectorizers[feature] = Vectorizer()
			trainVectors[feature] = vectorizers[feature].transform(candidateRelations,[feature],tfidf=tfidf)

		groupVector = None
		chosenFeatures = []
		prevScore,prevMatrix = -1.0, None
		while True:
			bestScore, bestFeature, bestMatrix = -1.0, None, None
			for feature in featureChoice:
				if prevMatrix is None:
					matrix = trainVectors[feature]
				else:
					matrix = hstack([prevMatrix,trainVectors[feature]])

				clf = svm.LinearSVC(class_weight='balanced')
				
				scores = cross_val_score(clf, matrix, classes, cv=5, scoring='f1_macro')
				score = scores.mean()

				#print chosenFeatures, feature, score, scores
				if score > bestScore:
					bestScore = score
					bestFeature = feature
					bestMatrix = matrix

			if bestScore > prevScore:
				# We see improvement
				featureChoice.remove(bestFeature)
				chosenFeatures.append(bestFeature)
				prevScore = bestScore
				prevMatrix = bestMatrix
			else:
				# No improvement made
				break

		return chosenFeatures

	def train(self,data):
		"""
		Does stuff
		"""
		assert isinstance(data,list)
		for d in data:
			assert isinstance(d,kindred.RelationData)
			
		self.candidateBuilder = CandidateBuilder()
		relTypes,candidateRelations,candidateClasses = self.candidateBuilder.build(data)
		
		self.relTypeToValidEntityTypes = defaultdict(set)
		
		self.relationToArgNames = {}
		for d in data:
			for r in d.getRelations():
				#print r.relationType, r.argNames
				entityIDsToEntities = d.getEntityIDsToEntities()
				relationEntities = [ entityIDsToEntities[eID] for eID in r.entityIDs ]
				validEntityTypes = tuple([ e.entityType for e in relationEntities ])
				
				self.relTypeToValidEntityTypes[r.relationType].add(validEntityTypes)
				
				if r.relationType in self.relationToArgNames:
					# TODO: Deal with relations with same name but different arguments nicely
					#assert self.relationToArgNames[r.relationType] == r.argNames, "%s != %s" % (str(self.relationToArgNames[r.relationType]), str(r.argNames))
					pass
				else:
					self.relationToArgNames[r.relationType] = r.argNames
			
		#print self.relationToArgNames
				
		self.classToRelType = { (i+1):relType for i,relType in enumerate(relTypes) }
		
		allClasses = set()
		for c in candidateClasses:
			allClasses.update(c)
		allClasses = sorted(list(allClasses))
		allClasses = [ c for c in allClasses if c != 0 ]
		
		self.allClasses = allClasses
	
		#options = ["ngrams","selectedngrams","bigrams","ngramsPOS","selectedngramsPOS","ngramsOfDependencyPath","bigramsOfDependencyPath","selectedTokenTypes","lemmas","selectedlemmas","dependencyPathElements","dependencyPathNearSelected","splitAcrossSentences","skipgrams_2","skipgrams_3","skipgrams_4","skipgrams_5","skipgrams_6","skipgrams_7","skipgrams_8","skipgrams_9","skipgrams_10","ngrams_betweenEntities","bigrams_betweenEntities"]

		# We'll just get the vectors for the selectedTokenTypes

		#tmpClassData = [ (1 in candidateClassGroup) for candidateClassGroup in candidateClasses ]

		#useSingleClassifier = False
		if self.useSingleClassifier:
			#chosenFeatures = ["selectedTokenTypes","dependencyPathElements","ngrams_betweenEntities","bigrams_betweenEntities","bigramsOfDependencyPath"]



			simplifiedClasses = []
			# TODO: Try sparse matrix rep
			for candidateRelation,candidateClassGroup in zip(candidateRelations,candidateClasses):
				#assert len(candidateClassGroup) == 1, "Cannot handle multiple relations with same set of entities " + str(candidateRelation)
				simplifiedClasses.append(candidateClassGroup[0])
			#print chosenFeatures
			#assert False
	
			if self.useBuilder:
				chosenFeatures = self.buildFeatureSet(candidateRelations,simplifiedClasses,self.tfidf)
			else:
				chosenFeatures = self.defaultFeatures

			self.vectorizer = Vectorizer()
			trainVectors = self.vectorizer.transform(candidateRelations,featureChoice=chosenFeatures,tfidf=self.tfidf)
		
			assert trainVectors.shape[0] == len(candidateClasses)
		
			if self.threshold is None:
				self.clf = svm.LinearSVC(class_weight='balanced')
			else:
				self.clf = Classifier_With_Threshold(self.threshold)
			self.clf.fit(trainVectors,simplifiedClasses)
		else:
			# TODO: Should we take into account the argument count when grouping classifiers?

			if not self.useBuilder:
				chosenFeatures = self.defaultFeatures

				self.vectorizer = Vectorizer()
				tmpMatrix = self.vectorizer.transform(candidateRelations,featureChoice=chosenFeatures,tfidf=self.tfidf)
			self.clfs = {}
			self.vectorizers = {}
			for c in self.allClasses:
				tmpClassData = [ (c in candidateClassGroup) for candidateClassGroup in candidateClasses ]

				if self.useBuilder:
					chosenFeatures = self.buildFeatureSet(candidateRelations,tmpClassData,self.tfidf)
					print(c, chosenFeatures)
					self.vectorizers[c] = Vectorizer()
					tmpMatrix = self.vectorizers[c].transform(candidateRelations,featureChoice=chosenFeatures,tfidf=self.tfidf)

				#save_sparse_csr('train.matrix',trainVectors.tocsr())
				#saveClasses('train.classes',tmpClassData)

				if self.threshold is None:
					self.clfs[c] = svm.LinearSVC(class_weight='balanced')
				else:
					self.clfs[c] = Classifier_With_Threshold(self.threshold)
				#self.clfs[c] = AdaBoostClassifier(n_estimators=2)
				#self.clfs[c].fit(trainVectors,tmpClassData)
				self.clfs[c].fit(tmpMatrix,tmpClassData)
		
		self.isTrained = True

	def predict(self,data):
		assert self.isTrained, "Classifier must be trained using train() before predictions can be made"
	
		assert isinstance(data,list)
		for d in data:
			assert isinstance(d,kindred.TextAndEntityData) or isinstance(d,kindred.RelationData)
			
		_,candidateRelations,testClasses = self.candidateBuilder.build(data)

		#if False:
		#	testVectors = self.vectorizer.transform(candidateRelations)
		#	tmpClassData = [ (1 in candidateClassGroup) for candidateClassGroup in testClasses ]
		#	print testVectors.shape
		
		
		#save_sparse_csr('test.matrix',testVectors.tocsr())
		#saveClasses('test.classes',tmpClassData)

		

		
		predictedRelations = []
		
		if self.useSingleClassifier:
			tmpMatrix = self.vectorizer.transform(candidateRelations)

			#predictedClasses = self.clfs[c].predict(testVectors)
			predictedClasses = self.clf.predict(tmpMatrix)
			for predictedClass,candidateRelation in zip(predictedClasses,candidateRelations):
				if predictedClass != 0:
					relType,nary = self.classToRelType[predictedClass]
					
					candidateRelationEntityTypes = tuple(candidateRelation.getEntityTypes())
					if not tuple(candidateRelationEntityTypes) in self.relTypeToValidEntityTypes[relType]:
						continue
					
					assert relType in self.relationToArgNames
					argNames = self.relationToArgNames[relType]
					assert not argNames is None

					predictedRelation = kindred.Relation(relType,list(candidateRelation.entitiesInRelation),argNames=argNames)
					predictedRelations.append(predictedRelation)
		else:
			if not self.useBuilder:
				tmpMatrix = self.vectorizer.transform(candidateRelations)

			for c in self.allClasses:

				if self.useBuilder:
					tmpMatrix = self.vectorizers[c].transform(candidateRelations)

				#predictedClasses = self.clfs[c].predict(testVectors)
				predicted = self.clfs[c].predict(tmpMatrix)
				for p,candidateRelation in zip(predicted,candidateRelations):
					if p != 0:
						relType,nary = self.classToRelType[c]
						
						candidateRelationEntityTypes = tuple(candidateRelation.getEntityTypes())
						if not tuple(candidateRelationEntityTypes) in self.relTypeToValidEntityTypes[relType]:
							continue
						
						assert relType in self.relationToArgNames
						argNames = self.relationToArgNames[relType]
						assert not argNames is None
						
						predictedRelation = kindred.Relation(relType,list(candidateRelation.entitiesInRelation),argNames=argNames)
						predictedRelations.append(predictedRelation)
					
		return predictedRelations
					
					
					
