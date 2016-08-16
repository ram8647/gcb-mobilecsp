__author__ = 'ehiller@css.edu'

import datetime

from models import transforms
from models.models import Student
from models.models import EventEntity
from models import utils as models_utils
from models import jobs
from models import event_transforms


from models.models import QuestionDAO
from models.models import QuestionGroupDAO

from models.models import MemcacheManager


class ActivityScoreParser(jobs.MapReduceJob):
    """class to parse the data returned with activities"""
    def __init__(self):
        """holds activity score info unit -> lesson -> question"""
        self.activity_scores = { }
        self.params = {}

    @staticmethod
    def get_description():
        return 'activity answers parser'

    @staticmethod
    def entity_class():
        return EventEntity

    @classmethod
    def _get_questions_by_question_id(cls, questions_by_usage_id):
        ret = {}
        ret['single'] = {}
        ret['grouped'] = {}
        for question in questions_by_usage_id.values():
            question_single = QuestionDAO.load(question['id'])
            if question_single:
                ret['single'][question['id']] = question_single
            else:
                question_group = QuestionGroupDAO.load(question['id'])
                if question_group:
                    ret['grouped'][question['id']] = {}
                    for item in question_group.items:
                        ret['grouped'][question['id']][item['question']] = QuestionDAO.load(item['question'])
        return ret

    def build_additional_mapper_params(self, app_context):
        questions_by_usage_id = event_transforms.get_questions_by_usage_id(app_context)
        return {
            'questions_by_usage_id':
                questions_by_usage_id,
            'valid_question_ids': (
                event_transforms.get_valid_question_ids()),
            'group_to_questions': (
                event_transforms.get_group_to_questions()),
            'assessment_weights':
                event_transforms.get_assessment_weights(app_context),
            'unscored_lesson_ids':
                event_transforms.get_unscored_lesson_ids(app_context),
            'questions_by_question_id':
                ActivityScoreParser._get_questions_by_question_id(questions_by_usage_id)
            }

    def parse_activity_scores(self, activity_attempt):
        if activity_attempt.source == 'tag-assessment':
            data = transforms.loads(activity_attempt.data)

            timestamp = int(
            (activity_attempt.recorded_on - datetime.datetime(1970, 1, 1)).total_seconds())

            questions = self.params['questions_by_usage_id']
            valid_question_ids = self.params['valid_question_ids']
            assessment_weights = self.params['assessment_weights']
            group_to_questions = self.params['group_to_questions']

            student_answers = self.activity_scores.get(Student.get_student_by_user_id(activity_attempt.user_id).email, {})

            answers = event_transforms.unpack_check_answers(
                data, questions, valid_question_ids, assessment_weights,
                group_to_questions, timestamp)

            #add score to right lesson
            question_info = questions[data['instanceid']]
            unit_answers = student_answers.get(question_info['unit'], {})
            lesson_answers = unit_answers.get(question_info['lesson'], {})

            for answer in answers:
                question_answer_dict = {}
                question_answer_dict['unit_id'] = answer.unit_id
                question_answer_dict['lesson_id'] = answer.lesson_id
                question_answer_dict['sequence'] = answer.sequence
                question_answer_dict['question_id'] = answer.question_id
                question_answer_dict['question_type'] = answer.question_type
                question_answer_dict['timestamp'] = answer.timestamp
                question_answer_dict['answers'] = answer.answers
                question_answer_dict['score'] = answer.score
                question_answer_dict['weighted_score'] = answer.weighted_score
                question_answer_dict['tallied'] = answer.tallied

                if answer.sequence in lesson_answers and lesson_answers[answer.sequence] < timestamp:
                    lesson_answers[answer.sequence] = question_answer_dict
                elif answer.sequence not in lesson_answers:
                    lesson_answers[answer.sequence] = question_answer_dict

            unit_answers[question_info['lesson']] = lesson_answers
            student_answers[question_info['unit']] = unit_answers

            self.activity_scores[Student.get_student_by_user_id(activity_attempt.user_id).email] = student_answers

        return self.activity_scores

    def build_missing_score(self, question, question_info, student_id, unit_id, lesson_id, sequence=-1):
        if sequence == -1:
            sequence = question['sequence']

        question_answer = None
        if unit_id in self.activity_scores[student_id] and lesson_id in \
                self.activity_scores[student_id][unit_id]:
            question_answer = next((x for x in self.activity_scores[student_id][unit_id][lesson_id].values()
                                    if x['sequence'] == sequence), None)

        possible_score = 0
        choices = None
        if question_info:
            if 'choices' in question_info.dict:
                choices = question_info.dict['choices']
                #calculate total possible points for questions
                for choice in choices:
                    if float(choice['score']) > 0:
                        possible_score += float(choice['score'])
            elif 'graders' in question_info.dict:
                choices = question_info.dict['graders']
                for grader in choices:
                    possible_score += float(grader['score'])
            if 'weight' in question and float(question['weight']) is not 0.0:
                possible_score = possible_score * float(question['weight'])
        else:
            possible_score = 1

        if not question_answer:
            question_answer_dict = {}
            question_answer_dict['unit_id'] = unit_id
            question_answer_dict['lesson_id'] = lesson_id
            question_answer_dict['sequence'] = sequence
            question_answer_dict['question_id'] = question['id']
            question_answer_dict['question_type'] = 'NotCompleted'
            question_answer_dict['timestamp'] = 0
            question_answer_dict['answers'] = ''
            question_answer_dict['score'] = 0
            question_answer_dict['weighted_score'] = 0
            question_answer_dict['tallied'] = False
            question_answer_dict['possible_points'] = possible_score
            question_answer_dict['choices'] = choices

            unit = self.activity_scores[student_id].get(unit_id, {})
            lesson = unit.get(lesson_id, {})
            lesson[sequence] = question_answer_dict
        else:
            question_answer_dict = {}
            question_answer_dict['unit_id'] = question_answer['unit_id']
            question_answer_dict['lesson_id'] = question_answer['lesson_id']
            question_answer_dict['sequence'] = question_answer['sequence']
            question_answer_dict['question_id'] = question_answer['question_id']
            question_answer_dict['question_type'] = question_answer['question_type']
            question_answer_dict['timestamp'] = question_answer['timestamp']
            question_answer_dict['answers'] = question_answer['answers']
            question_answer_dict['score'] = question_answer['score']
            question_answer_dict['weighted_score'] = question_answer['weighted_score']
            question_answer_dict['tallied'] = question_answer['tallied']
            question_answer_dict['possible_points'] = possible_score
            question_answer_dict['choices'] = choices

            self.activity_scores[student_id][unit_id][lesson_id][sequence] = question_answer_dict

    def build_missing_scores(self):
         #validate total points for lessons, need both question collections for score and weight
        questions = self.params['questions_by_usage_id']
        questions_info = self.params['questions_by_question_id']
        for student_id in self.activity_scores:
            for question in questions.values():
                unit_id = question['unit']
                lesson_id = question['lesson']

                question_info = questions_info['single'].get(question['id'], None) #next((x for x in questions_info if x
                #  and
                # x.id == question['id']), None)
                if not question_info:
                    question_info_group = questions_info['grouped'][question['id']]
                    sequence = question['sequence']
                    for question_info in question_info_group.values():
                        self.build_missing_score(question, question_info, student_id, unit_id, lesson_id, sequence)
                        sequence += 1
                else:
                    self.build_missing_score(question, question_info, student_id, unit_id, lesson_id)

    @classmethod
    def get_activity_scores(cls, student_user_ids, course, force_refresh = False):
        """Retrieve activity data for student using EventEntity"""

        #instantiate parser object
        cached_date = datetime.datetime.now()
        activityParser = ActivityScoreParser()

        if force_refresh:
            activityParser.params = activityParser.build_additional_mapper_params(course.app_context)

            for user_id in student_user_ids:
                mapper = models_utils.QueryMapper(
                    EventEntity.all().filter('user_id in', [user_id]), batch_size=500, report_every=1000)

                def map_fn(activity_attempt):
                    activityParser.parse_activity_scores(activity_attempt)

                mapper.run(map_fn)

            activityParser.build_missing_scores()

            #Lets cache results for each student
            for user_id in student_user_ids:
                cached_student_data = {}
                cached_student_data['date'] = cached_date
                cached_student_data['scores'] = activityParser.activity_scores.get(Student.get_student_by_user_id(
                    user_id).email, {})
                MemcacheManager.set(cls._memcache_key_for_student(Student.get_student_by_user_id(user_id).email),
                                    cached_student_data)
        else:
            uncached_students = []
            for student_id in student_user_ids:
                scores_for_student = MemcacheManager.get(cls._memcache_key_for_student(Student.get_student_by_user_id(
                    student_id).email))
                if scores_for_student:
                    cached_date = scores_for_student['date']
                    activityParser.activity_scores[student_id] = scores_for_student['scores']
                else:
                    uncached_students.append(student_id)
            if len(uncached_students) > 0:
                if cached_date == None or datetime.datetime.now() < cached_date:
                    cached_date = datetime.datetime.now()

                activityParser.params = activityParser.build_additional_mapper_params(course.app_context)

                for user_id in uncached_students:
                    mapper = models_utils.QueryMapper(
                        EventEntity.all().filter('user_id in', [user_id]), batch_size=500, report_every=1000)

                    def map_fn(activity_attempt):
                        activityParser.parse_activity_scores(activity_attempt)

                    mapper.run(map_fn)

                activityParser.build_missing_scores()

                #Lets cache results for each student
                for user_id in uncached_students:
                    cached_student_data = {}
                    cached_student_data['date'] = cached_date
                    cached_student_data['scores'] = activityParser.activity_scores.get(Student.get_student_by_user_id(
                        user_id).email, {})
                    MemcacheManager.set(cls._memcache_key_for_student(Student.get_student_by_user_id(user_id).email),
                                        cached_student_data)

        score_data = {}
        score_data['date'] = cached_date
        score_data['scores'] = activityParser.activity_scores

        return score_data

    @classmethod
    def _memcache_key_for_student(cls, user_id):
        return ('activityscores:%s' % user_id)


class StudentProgressTracker(object):
    """Gets student progress for a given course.

    Note:
        Gets progress at the unit, lesson, and course levels.

    """

    @classmethod
    def get_unit_completion(cls, student, course):
        """Gets completion progress for all units in a course for a student"""
        tracker = course.get_progress_tracker()

        return tracker.get_unit_percent_complete(student)

    @classmethod
    def get_overall_progress(cls, student, course):
        """Gets progress at the course level for a student"""
        tracker = course.get_progress_tracker()

        unit_completion = tracker.get_unit_percent_complete(student)

        course_completion = 0
        for unit_completion_value in unit_completion.values():
            course_completion += unit_completion_value

        #return percentages
        course_completion = (course_completion / len(unit_completion)) * 100

        return course_completion

    @classmethod
    def get_detailed_progress(cls, student, course, include_assessments = False):
        """Gets unit and lesson completion for in a course for a student"""
        units = []

        tracker = course.get_progress_tracker()

        progress = tracker.get_or_create_progress(student)
        unit_completion = tracker.get_unit_percent_complete(student)

        course_units = course.get_units()
        if not include_assessments:
            course_units = filter(lambda x: x.type == 'U', course_units)

        for unit in course_units:
            # Don't show assessments that are part of units.
            if course.get_parent_unit(unit.unit_id):
                continue

            if unit.unit_id in unit_completion:
                lessons = course.get_lessons(unit.unit_id)
                lesson_status = tracker.get_lesson_progress(student, unit.unit_id, progress)
                lesson_progress = []
                for lesson in lessons:
                    lesson_progress.append({
                        'lesson_id': lesson.lesson_id,
                        'title': lesson.title,
                        'completion': lesson_status[lesson.lesson_id]['html'],
                    })
                    activity_status = tracker.get_activity_status(progress, unit.unit_id, lesson.lesson_id)
                units.append({
                    'unit_id': unit.unit_id,
                    'title': unit.title,
                    'labels': list(course.get_unit_track_labels(unit)),
                    'completion': unit_completion[unit.unit_id],
                    'lessons': lesson_progress,
                    })
        return units