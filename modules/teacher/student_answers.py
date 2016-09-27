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

    # TODO: Duplicate over student_activities.py table.  Move to a single location.
    QUIZLY_DESCRIPTIONS = {  
        'LXgF4NO50hNM':'Quizly, Pause the Player',       # Unit 2
        'BtQ8hSoGkeml':'Quizly, Stop the Player',
        'Dstsv7VuDQb5':'Quizly, Stop Player if playing',
        'twxBgieSEwqs':'Quizly, If/else stop/start Player', 
        'a3uBZXYSOJee':'Quizly, Set background color',   # Unit 3
        'pnhvzarYPPW1':'Quizly, Set text color',
        'G3qzTftPYKTe':'Quizly, Increment a variable',
        '4kITN7u5hdsO':'Quizly, Initialize global variable',
        'pCZugPUxlHeb':'Quizly, Initializing',
        '8T30OkUf5r1r':'Quizly, Simple if/else',
        'KQctST8skmaC':'Quizly, Procedure to double a variable',
        'v2m4Ks25S1MX':'Quizly, Procedure to add globals',
        'rCgLbJRceEbn':'Quizly, Procedure to reset the score',          # Unit 4   
        '7uowepixSjT4':'Quizly, Procedure to calculate the hit rate',
        'w18q4UWKxvlM':'Quizly, Fix a bug in updateScore procedure',
        'rvjUJMaLZ56s':'Quizly, If/else greater than',
        'scgF2VSCjUv8':'Quizly, Simple if/else',    # Unit 5
        'JatcV7u6GOer':'Quizly, If x greater than y',   
    }

    @classmethod
    def record(cls, user, data):
        """Records a student tag-assessment into a datastore.
  
           A tag-assessment includes a student attempt at a quiz question.

           The user's email is used as the key for the StudentAnswersEntity. 
        """
        email = user.email()
        key = db.Key.from_path('StudentAnswersEntity', email)
        logging.debug('***RAM*** email ' + email + ' key = ' + str(key))
        student = db.get(key)
        if student: 
            student.answers_dict = cls.update_answers_dict(student, data, user)
            student.recorded_on = datetime.datetime.now()
            student.put()
        else:
            student = cls(key_name = email)
            dict = cls.update_answers_dict(None, data, user)
#            logging.debug('***RAM*** student ' + str(dict))
            student.answers_dict = dict
            student.user_id = user.user_id()
            student.email = user.email() 
            student.put()

    @classmethod
    def update_answers_dict(cls, student, data, user):
        if student:    # Student dict already exists
            data_json = json.loads(data)
            dict = json.loads(student.answers_dict)
            dict = cls.build_dict(dict, data, user)
            return json.dumps(dict)
        else:
            dict = cls.build_dict(None, data, user)  # New student Dict
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
        if 'answer' in data_json:           # Takes care of SA_questions? that are missing answer?
             answers = data_json['answer']
        else:
             answer = [False]           # An array b/c of multi choice with multiple correct answers
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
        """ Retrieve the answers dict for a student. """
        email = student.email
        logging.warning('***RAM*** get answers dict for student, email = ' + email)
        key = db.Key.from_path('StudentAnswersEntity', email)
        logging.debug('***RAM*** email ' + email + ' key = ' + str(key))
        student_answers = db.get(key)
        dict = json.loads(student_answers.answers_dict)
#        logging.debug('***RAM*** answers dict =  ' + str(dict))
        if student_answers:
            return dict
        return {}

    def put(self):
        """Do the normal put() and also invalidate memcache."""
        result = super(StudentAnswersEntity, self).put()
        MemcacheManager.delete(self.memcache_key)
        return result

    def delete(self):
        """Do the normal delete() and invalidate memcache."""
        super(StudentAnswersEntity, self).delete()
        MemcacheManager.delete(self.memcache_key)

