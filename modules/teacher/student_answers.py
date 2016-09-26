# Copyright 2016 Mobile CSP Project. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Contains the TeacherEntity and TeacherItemRESTHandler

import datetime
import logging
import json
import random 
import copy

from google.appengine.ext import db

from common import schema_fields
from common import utils as common_utils

#from controllers import utils

from models import entities
from models import models
#from models import resources_display
#from models import roles
#from models import transforms
#from models import event_transforms

#from models.models import QuestionDAO
#from models.models import QuestionGroupDAO
from models.models import MemcacheManager

class StudentAnswersEntity(entities.BaseEntity):

    """A class that represents a persistent database entity for student answers."""
    recorded_on = db.DateTimeProperty(auto_now_add=True, indexed=True)
    user_id = db.StringProperty(indexed=True)
    email = db.StringProperty(indexed=True) 
    answers_dict = db.TextProperty(indexed=False)   #json string
    
    memcache_key = 'studentanswers'

    # Static lookup tables
    questions_data_dict = None

    QUIZLY_DESCRIPTIONS = {  
        'LXgF4NO50hNM':'Pause the Player',       # Unit 2
        'BtQ8hSoGkeml':'Stop the Player',
        'Dstsv7VuDQb5':'Stop Player if playing',
        'twxBgieSEwqs':'If/else stop/start Player', 
        'a3uBZXYSOJee':'Set background color',   # Unit 3
        'pnhvzarYPPW1':'Set text color',
        'G3qzTftPYKTe':'Increment a variable',
        '4kITN7u5hdsO':'Initialize global variable',
        'pCZugPUxlHeb':'Initializing',
        '8T30OkUf5r1r':'Simple if/else',
        'KQctST8skmaC':'Procedure to double a variable',
        'v2m4Ks25S1MX':'Procedure to add globals',
        'rCgLbJRceEbn':'Procedure to reset the score',          # Unit 4   
        '7uowepixSjT4':'Procedure to calculate the hit rate',
        'w18q4UWKxvlM':'Fix a bug in updateScore procedure',
        'rvjUJMaLZ56s':'If/else greater than',
    }
        
    @classmethod
    def record(cls, user, data):
        """Records new student tag-assessment into a datastore."""

#        logging.debug('***RAM*** data ' + str(data))
        found = False
        students = StudentAnswersEntity.all()
        for student in students:
#            logging.debug('***RAM*** student ' + str(student))
            if student.user_id == user.user_id():
                student.answers_dict = cls.update_answers_dict(student, data, user)
                student.recorded_on = datetime.datetime.now()
                student.put()
                found = True
                return
        if not found:
            student = cls()
            dict = cls.update_answers_dict(None, data, user)
#            logging.debug('***RAM*** student ' + str(dict))
            student.answers_dict = dict
            student.user_id = user.user_id()
            student.email = user.email() 
        student.put()

    @classmethod
    def update_answers_dict(cls, student, data, user):
        if student:    # student already exists
            data_json = json.loads(data)
            dict = json.loads(student.answers_dict)
            dict = cls.build_dict(dict, data, user)
            return json.dumps(dict)
        else:
            dict = cls.build_dict(None, data, user)  # new student
#            logging.debug('***RAM*** dict ' + str(dict))
            return json.dumps(dict)

    @classmethod
    def build_dict(cls, dict, data, user):
        """ Builds a dict for recording student performance on questions.

           The dict is indexed by student email and id and contains a complete
           record of the students scores and attempts for questions and Quizly
           exercises.

           POLICY: The score recorded is the last score recorded.  So if a
           student gets a question correct and then redoes it and gets it wrong,
           the wrong answer and score of 0 is what would be recorded here.
           Should this be changed?
        """
        data_json = json.loads(data)
        url = data_json['location']
        unit_id =  str(url[url.find('unit=') + len('unit=') : url.find('&lesson=')])
        lesson_id = str(url[ url.find('&lesson=') + len('&lesson=') : ])
        instance_id = data_json['instanceid']
        if 'answer' in data_json:           # Takes care of legacy events that are missing answer?
             answers = data_json['answer']
             logging.warning('***RAM*** data contains answer property ' + str(data_json))
        else:
             logging.warning('***RAM*** data missing answer property ' + str(data_json))
             answer = [False]           # An array b/c of multi choice with multiple correct answers
#        answers = data_json['answer']     # An array b/c of multi choice with multiple correct answers
        score = data_json['score']
        type = data_json['type']
        quid = None
        if 'quid' in data_json:          # Regular (not Quizly) question
            quid = data_json['quid']
        if not dict:
            dict = {}
            dict['email'] = user.email()
            dict['user_id'] = user.user_id()
            dict['answers'] = cls.build_answers_dict(None, unit_id, lesson_id, instance_id, quid, answers, score, type)
        else:
            answers_dict = dict['answers']
            dict['answers'] = cls.build_answers_dict(answers_dict, unit_id, lesson_id, instance_id, quid, answers, score, type)
        return dict

    @classmethod
    def build_answers_dict(cls, answers_dict, unit_id, lesson_id, instance_id, quid, answers, score, type):
        """ Builds the answers dict.

            Takes the form:
            answers = {unit_id: {lesson_id: {instance_id: {<answer data>}}}}

            The rest of the data -- e.g., sequence,choices -- has to be computed when the data 
            are sent to the client.
        """

        timestamp = int((datetime.datetime.now() - datetime.datetime(1970, 1, 1)).total_seconds())
        attempt = {'question_id': quid, 'answers': answers, 'score': score, 
                   'attempts': 1, 'question_type':type, 'timestamp': timestamp,
                   # Not sure whether the rest are needed
                   'weighted_score': 1, 'lesson_id': lesson_id, 'unit_id': unit_id, 'possible_points': 1, 
                   'tallied': False,
                 }
        if answers == 'true' or answers == 'false':   # Quizly answers, put into an array
            attempt['answers'] = [ answers ]          
#        logging.debug('***RAM*** Quizly answers = ' + str(answers) + ' a= '  + str(attempt['answers']))
        if not answers_dict:
            answers_dict = {}
            lesson = {instance_id: attempt }
            unit = {lesson_id: lesson }
            answers_dict = {unit_id: unit }
        else:
            if unit_id in answers_dict:
                if lesson_id in answers_dict[unit_id]:
                    if instance_id in answers_dict[unit_id][lesson_id]:
                        answers_dict[unit_id][lesson_id][instance_id]['attempts'] += 1
                        answers_dict[unit_id][lesson_id][instance_id]['score'] = score
                    else:
                        answers_dict[unit_id][lesson_id][instance_id] = attempt
                else:
                    lesson = {instance_id: attempt}
                    answers_dict[unit_id][lesson_id] = lesson
            else:
                lesson = {instance_id: attempt}
                unit = {lesson_id: lesson}
                answers_dict[unit_id] = unit
        return answers_dict

    @classmethod
    def get_answers_dict_for_student(cls, student):
        students = cls.get_students()
        scores = None
        for stud in students:
#            logging.debug('***RAM*** ' + str(stud) + ' ' + str(student))        
            if stud.user_id == student.user_id:
                return json.loads(stud.answers_dict)
        return {}
        
    @classmethod
    def get_students(cls, allow_cached = True):
        students = MemcacheManager.get(cls.memcache_key)
        if not allow_cached or students is None:
            students = StudentAnswersEntity.all()
            MemcacheManager.set(cls.memcache_key, students)
        return students


#     @classmethod
#     def get_scores(cls, student, course, force_refresh = True):

#         cached_date = datetime.datetime.now()
#         if force_refresh:
#             questions_data_dict = cls.build_questions_data(course.app_context)
#         else:
#             if not questions_data_dict:
#                 questions_data_dict = cls.build_questions_data(course.app_context)

#         answers_dict = cls.get_answers_dict_for_student(student)
#         if answers_dict == {}:
#             return {}

#         # NOTE: We're ignoring question groups
#         questions_by_quid = questions_data_dict['questions_by_question_id']['single']

#         attempts = {}
        
#         # Add sequence numbers, descriptions, choices, possible points  to answers dict
#         answers = answers_dict['answers']
#         for unit_id in answers:
#             for lesson_id in answers[unit_id]:
#                 for instance_id in answers[unit_id][lesson_id]:

#                     # Quizly question -- add description and choices and make some adjustments
#                     if not instance_id in questions_data_dict['questions_by_usage_id']: 
#                         if instance_id in cls.QUIZLY_DESCRIPTIONS:
#                             answers[unit_id][lesson_id][instance_id]['description'] = \
#                                 cls.QUIZLY_DESCRIPTIONS[instance_id]
#                         else:
#                             answers[unit_id][lesson_id][instance_id]['description'] = "Quizly " + instance_id
#                         answers[unit_id][lesson_id][instance_id]['choices'] = \
#                             [{'score':1, 'text':'T'}, {'score':0, 'text':'F'}]
#                         sequence = random.randint(10,30)
#                         answers[unit_id][lesson_id][instance_id]['sequence'] = sequence
#                         answers[unit_id][lesson_id][instance_id]['question_id'] = instance_id
#                         answers[unit_id][lesson_id][instance_id]['question_type'] = 'Quizly'
#                         attempts[instance_id] = answers[unit_id][lesson_id][instance_id]['attempts']

#                     # Regular question -- add sequence, weight, description and choices and possible points
#                     else:
#                         data = questions_data_dict['questions_by_usage_id'][instance_id]
#                         sequence = data['sequence']
#                         answers[unit_id][lesson_id][instance_id]['sequence'] = sequence
#                         answers[unit_id][lesson_id][instance_id]['weight'] = data['weight']
#                         quid = answers[unit_id][lesson_id][instance_id]['question_id']
#                         question_info = questions_by_quid.get(quid, None)
#                         attempts[quid] = answers[unit_id][lesson_id][instance_id]['attempts']

#                         if question_info:
#                             desc = question_info.dict['description']
#                             answers[unit_id][lesson_id][instance_id]['description'] = desc
#                             if 'choices' in question_info.dict:
#                                 possible_score = 0
#                                 choices = question_info.dict['choices']
#                                 choices_scores_only = []
#                                 i = 0

#                                 # Iterate through choices and calculate total possible score, usually 1
#                                 # If it's never != 1, maybe this can be eliminated
#                                 for choice in choices:
#                                     if float(choice['score']) > 0:
#                                         possible_score += float(choice['score'])
#                                     choices_scores_only.append(  {'score':choice['score'], 
#                                                                   'text':chr(ord('A') + i) } )
#                                     i += 1
#                                 answers[unit_id][lesson_id][instance_id]['choices'] = choices_scores_only
#                                 answers[unit_id][lesson_id][instance_id]['possible_points'] = possible_score
                        
#         # We were using instance_id as key. We need to return with sequence as key.
#         newanswers = cls.replace_instanceid_with_sequence_key(answers)
#         newdict = {}
#         newdict['attempts'] = attempts
#         newdict['scores'] = newanswers
#         return newdict

#     @classmethod 
#     def replace_instanceid_with_sequence_key(cls, dict):
#         newanswers = copy.deepcopy(dict)
#         for unit_id in dict:
#             for lesson_id in dict[unit_id]:
#                 for instance_id in dict[unit_id][lesson_id]:
#                     sequence = dict[unit_id][lesson_id][instance_id]['sequence']
#                     pop = newanswers[unit_id][lesson_id].pop(instance_id)
#                     newanswers[unit_id][lesson_id][sequence] = pop
#         return newanswers

#     @classmethod
#     def build_questions_data(cls, app_context):
#         logging.debug('***RAM***  Trace: build_questions_data() ')

#         questions_by_usage_id = event_transforms.get_questions_by_usage_id(app_context)
# #         logging.debug('***RAM*** questions_by_usage_id ' + str(questions_by_usage_id))
# #         logging.debug('***RAM*** valid_question_ids ' + str(event_transforms.get_valid_question_ids()))
# #         logging.debug('***RAM*** assessment_weights ' + str(event_transforms.get_assessment_weights(app_context)))
# #         logging.debug('***RAM*** unscored_lesson_ids ' + str(event_transforms.get_unscored_lesson_ids(app_context)))
# #        logging.debug('***RAM*** questions_by_question_id ' + str(cls._get_questions_by_question_id(questions_by_usage_id)))
#         return {
#             'questions_by_usage_id':
#                 questions_by_usage_id,
# #             'valid_question_ids': (
# #                 event_transforms.get_valid_question_ids()),
# #             'group_to_questions': (
# #                 event_transforms.get_group_to_questions()),
# #             'assessment_weights':
# #                 event_transforms.get_assessment_weights(app_context),
# #             'unscored_lesson_ids':
# #                 event_transforms.get_unscored_lesson_ids(app_context),
#             'questions_by_question_id':
#                 cls._get_questions_by_question_id(questions_by_usage_id)
#             }

#     @classmethod
#     def _get_questions_by_question_id(cls, questions_by_usage_id):
#         ''' Retrieves every question in the course returning 
#             them in a dict:  { id:questionDAO, ... }

#             @param questions_by_usage_id.values() is a dict:
#              {unit, lesson, sequence, weight, quid}
#         '''
#         ret = {}
#         ret['single'] = {}
#         ret['grouped'] = {}
#         for question in questions_by_usage_id.values():
#             question_single = QuestionDAO.load(question['id'])
#             if question_single:
#                 ret['single'][question['id']] = question_single
#             else:
#                 question_group = QuestionGroupDAO.load(question['id'])
#                 if question_group:
#                     ret['grouped'][question['id']] = {}
#                     for item in question_group.items:
#                         ret['grouped'][question['id']][item['question']] = QuestionDAO.load(item['question'])
#         return ret


    def put(self):
        """Do the normal put() and also invalidate memcache."""
        result = super(StudentAnswersEntity, self).put()
        MemcacheManager.delete(self.memcache_key)
        return result

    def delete(self):
        """Do the normal delete() and invalidate memcache."""
        super(StudentAnswersEntity, self).delete()
        MemcacheManager.delete(self.memcache_key)

