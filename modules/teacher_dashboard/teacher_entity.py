'''Create a teacher's entity'''

__author__ = 'barok.imana@trincoll.edu'


from models.entities import BaseEntity

from models.models import MemcacheManager
from models.models import PersonalProfile
from models.models import PersonalProfileDTO
from models.models import Student
from models.models import BaseJsonDao

from models import transforms

from google.appengine.ext import db
from google.appengine.api import namespace_manager
from google.appengine.api import users

import appengine_config
import logging
import datetime
import json
from json import JSONEncoder

from common import utils as common_utils


# We want to use memcache for both objects that exist and do not exist in the
# datastore. If object exists we cache its instance, if object does not exist
# we cache this object below.
NO_OBJECT = {}

class Teacher(BaseEntity):
    """Teacher data specific to a course instance, modeled after the student Entity"""
    enrolled_on = db.DateTimeProperty(auto_now_add=True, indexed=True)
    user_id = db.StringProperty(indexed=True)
    name = db.StringProperty(indexed=False)
    additional_fields = db.TextProperty(indexed=False)
    is_enrolled = db.BooleanProperty(indexed=False)
    is_active = db.BooleanProperty(indexed=False)

    # Additional field for teachers
    sections = db.TextProperty(indexed=False)
    school = db.StringProperty(indexed=False)
    email = db.StringProperty(indexed=False)

    _PROPERTY_EXPORT_BLACKLIST = [
        additional_fields,  # Suppress all additional_fields items.
        # Convenience items if not all additional_fields should be suppressed:
        #'additional_fields.xsrf_token',  # Not PII, but also not useful.
        #'additional_fields.form01',  # User's name on registration form.
        name]

    @classmethod
    def get_student_by_email(self, email):
        """Gets a student from DB using email. v1.10 no longer allows retrieving students
           by email because there can be more than one student associated with an email??
           This is a workaround.
        """    
        # v1.110 changes the way students are retrieved. get_first_by_email() returns a tuple of
        #  the form (Student, unique).   We are ignoring the unique flag here.

        student_by_email = Student.get_first_by_email(email)

        if not student_by_email:
            return None

        student = student_by_email[0]
        if not student:
            return None
 
        return student

    @classmethod
    def safe_key(cls, db_key, transform_fn):
        return db.Key.from_path(cls.kind(), transform_fn(db_key.id_or_name()))

    def for_export(self, transform_fn):
        """Creates an ExportEntity populated from this entity instance."""
        assert not hasattr(self, 'key_by_user_id')
        model = super(Teacher, self).for_export(transform_fn)
        model.user_id = transform_fn(self.user_id)
        # Add a version of the key that always uses the user_id for the name
        # component. This can be used to establish relationships between objects
        # where the student key used was created via get_key(). In general,
        # this means clients will join exports on this field, not the field made
        # from safe_key().
        model.key_by_user_id = self.get_key(transform_fn=transform_fn)
        return model

    @classmethod
    def _memcache_key(cls, key):
        """Makes a memcache key from primary key."""
        return 'entity:teacher:%s' % key

    @classmethod
    def _memcache_key(cls, key):
        """Makes a memcache key from primary key."""
        return 'entity:teacher:%s' % key

    def put(self):
        """Do the normal put() and also add the object to memcache."""
        result = super(Teacher, self).put()
        MemcacheManager.set(self._memcache_key(self.key().name()), self)
        return result

    def delete(self):
        """Do the normal delete() and also remove the object from memcache."""
        super(Teacher, self).delete()
        MemcacheManager.delete(self._memcache_key(self.key().name()))

    @classmethod
    def add_new_teacher_for_user(
        cls, email, school, additional_fields, alerts):
        TeacherProfileDAO.add_new_teacher_for_user(email, school, additional_fields, alerts)

    @classmethod
    def update_teacher_for_user(cls, email, school, active, additional_fields, alerts):
        TeacherProfileDAO.update_teacher_for_user(email, school, active, additional_fields, alerts)

    @classmethod
    def get_by_email(cls, email):
        return Teacher.get_by_key_name(email.encode('utf8'))

    @classmethod
    def get_teacher_by_user_id(cls):
        """Loads user and student and asserts both are present."""
        user = users.get_current_user()
        if not user:
            raise Exception('No current user.')
        teacher = cls.get_by_email(user.email())
        if not teacher:
            raise Exception('Teacher instance corresponding to user %s not '
                            'found.' % user.email())
        return teacher

    @classmethod
    def get_teacher_by_user_id(cls, user_id):
        teachers = cls.all().filter(cls.user_id.name, user_id).fetch(limit=2)
        if len(teachers) == 2:
            raise Exception(
                'There is more than one teacher with user_id %s' % user_id)
        return teachers[0] if teachers else None

    @classmethod
    def get_teacher_by_email(cls, email):
        """Returns enrolled teacher or None."""
        # ehiller - not sure if memcache check is in the right place, feel like we might want to do that after
        # checking datastore. this depends on what memcachemanager returns if a teacher hasn't been set there yet but
        #  still actually exists.
        teacher = MemcacheManager.get(cls._memcache_key(email))
        if NO_OBJECT == teacher:
            return None
        if not teacher:
            teacher = Teacher.get_by_email(email)
            if teacher:
                MemcacheManager.set(cls._memcache_key(email), teacher)
            else:
                MemcacheManager.set(cls._memcache_key(email), NO_OBJECT)
        if teacher: #ehiller - removed isEnrolled check, don't think we still need a teacher to be
        # enrolled to get their data back
            return teacher
        else:
            return None

    @classmethod
    def get_all_teachers_for_course(cls):
        """Returns all enrolled teachers or None."""

        teachers = []

        for teacher in TeacherProfileDAO.get_all_iter():
            teachers.append(teacher)

        if not teachers:
            return None

        return teachers

    def get_key(self, transform_fn=None):
        """Gets a version of the key that uses user_id for the key name."""
        if not self.user_id:
            raise Exception('Teacher instance has no user_id set.')
        user_id = transform_fn(self.user_id) if transform_fn else self.user_id
        return db.Key.from_path(Teacher.kind(), user_id)

    def has_same_key_as(self, key):
        """Checks if the key of the teacher and the given key are equal."""
        return key == self.get_key()

class TeacherProfileDAO(object):
    """All access and mutation methods for PersonalProfile and Teacher."""

    TARGET_NAMESPACE = appengine_config.DEFAULT_NAMESPACE_NAME
    ENTITY = Teacher

    # Each hook is called back after update() has completed without raising
    # an exception.  Arguments are:
    # profile: The PersonalProfile object for the user
    # student: The Student object for the user
    # Subsequent arguments are identical to the arguments list to the update()
    # call.  Not documented here so as to not get out-of-date.
    # The return value from hooks is discarded.  Since these hooks run
    # after update() has succeeded, they should run as best-effort, rather
    # than raising exceptions.
    UPDATE_POST_HOOKS = []

    # Each hook is called back after _add_new_student_for_current_user has
    # completed without raising an exception.  Arguments are:
    # student: The Student object for the user.
    # The return value from hooks is discarded.  Since these hooks run
    # after update() has succeeded, they should run as best-effort, rather
    # than raising exceptions.
    ADD_STUDENT_POST_HOOKS = []

    @classmethod
    def _memcache_key(cls, key):
        """Makes a memcache key from primary key."""
        return 'entity:personal-profile:%s' % key

    # This method is going to largely depend on how we plan to register
    # users as teachers

    @classmethod
    def add_new_teacher_for_user(
            cls, email,  school, additional_fields, alerts):

#         student_by_email = Student.get_first_by_email(email)

#         if not student_by_email:
#             alerts.append('This email is not registered as a student for this course')
#             return None

#         # v1.110 changes the way students are retrieved. get_first_by_email() returns a tuple of
#         #  the form (Student, unique).   We are ignoring the unique flag here.

#         student = student_by_email[0]
#         if not student:
#             alerts.append('This email is not registered as a student for this course')
#             return None

        student = Teacher.get_student_by_email(email)
        if not student:        
            alerts.append('This email is not registered as a student for this course')
            return None
        else:
            # assume a new teacher is active by default
            teacher = cls._add_new_teacher_for_user(
                student.user_id, email, student.name, school, True, additional_fields)

            if teacher:
                alerts.append('Teacher was successfully registered')

            return teacher

    @classmethod
    def update_teacher_for_user(cls, email, school, active, additional_fields, errors):
        teacher = Teacher.get_by_email(email)

        if not teacher:
            errors.append('No teacher exists associated with that email.')
            return None

        teacher = cls._update_teacher_for_user_in_txn(teacher.user_id, email, teacher.name, school, active,
                                                                                      additional_fields, errors)

        return teacher

    @classmethod
    def _add_new_teacher_for_user(
            cls, user_id, email, nick_name, school, active, additional_fields):
        teacher = cls._add_new_teacher_for_user_in_txn(
            user_id, email, nick_name, school, active, additional_fields)
        #ehiller - may need to add hooks for adding a teacher
        #common_utils.run_hooks(cls.ADD_STUDENT_POST_HOOKS, student)
        return teacher

    @classmethod
    @db.transactional(xg=True)
    def _add_new_teacher_for_user_in_txn(
            cls, user_id, email, nick_name, school, active, additional_fields):
        """Create new teacher."""

        # create profile if does not exist
        # profile = cls._get_profile_by_user_id(user_id)
        # if not profile:
        #     profile = cls._add_new_profile(user_id, email)

        # create new teacher
        teacher = Teacher.get_by_email(email)
        if not teacher:
            teacher = Teacher(key_name=email)

        # update profile
        #cls._update_attributes(
        #    profile, teacher, nick_name=nick_name, is_enrolled=True,
         #   labels=labels)

        # update student
        teacher.user_id = user_id
        teacher.additional_fields = additional_fields
        teacher.school = school
        teacher.name = nick_name
        teacher.is_active = active
        teacher.email = email

        # put both
        #cls._put_profile(profile)
        teacher.put()

        return teacher

    @classmethod
    def _update_teacher_for_user_in_txn(cls, user_id, email, nick_name, school, active, additional_fields, errors):
        #probably a better idea to get by user_id since the email may have been changed
        teacher = Teacher.get_teacher_by_user_id(user_id)
        if not teacher:
            errors.append('No teacher exists associated with that email')

        #not actually letting them update their email, used as key
        teacher.name = nick_name
        teacher.school = school
        teacher.additional_fields = additional_fields
        teacher.is_active = active

        teacher.put()

        return teacher

    @classmethod
    def get_all_iter(cls):
        """Return a generator that will produce all DTOs of a given type.

        Yields:
          A DTO for each row in the Entity type's table.
        """

        prev_cursor = None
        any_records = True
        while any_records:
            any_records = False
            query = cls.ENTITY.all().with_cursor(prev_cursor)
            for entity in query.run():
                any_records = True
                teacher = Teacher()
                teacher.email = entity.email
                teacher.user_id = entity.user_id
                teacher.name = entity.name
                teacher.is_active = entity.is_active
                teacher.school = entity.school
                if entity.sections:
                    teacher.sections = entity.sections

                yield teacher
            prev_cursor = query.cursor()


class CourseSectionEntity(object):

    """Course section information"""
    created_datetime = str(datetime.MINYEAR)
    section_id = ""
    section_name = ""
    section_description = ""
    students = ""
    is_active = False
    section_year = ""

    def __init__(self, course_section_decoded = None):
        if course_section_decoded:
            #self.created_datetime = course_section_decoded['created_datetime']
            self.section_id = course_section_decoded['id']
            self.section_name = course_section_decoded['name']
            self.section_description = course_section_decoded['description']
            self.students = course_section_decoded['students']
            self.is_active = course_section_decoded['active']
            if 'year' in course_section_decoded:
                self.section_year = course_section_decoded['year']

    def get_key(self):
        user = users.get_current_user()

        if not user:
            return None

        temp_key = user.email() + '_' + self.section_name.replace(' ', '').lower() + self.section_year

        return temp_key

    @classmethod
    def json_encoder(cls, obj):
        if isinstance(obj, cls):
            return {
                'id': obj.section_id,
                'name': obj.section_name,
                'description': obj.section_description,
                'active': obj.is_active,
                'students': obj.students,
                'year': obj.section_year
            }
        return None

    @classmethod
    def add_new_course_section(cls, section_id, new_course_section, errors):

        #initialize new course section
        course_section = CourseSectionEntity()

        user = users.get_current_user()

        if not user:
            errors.append('Unable to add course section. User not found.')
            return False

        #if section_id == None or len(section_id) == 0:
        #    section_id = user.email() + '_' + new_course_section.name.replace(' ', '')

        #course_section.section_id = section_id
        course_section.section_name = new_course_section.name
        course_section.section_description = new_course_section.description
        course_section.is_active = new_course_section.active
        course_section.section_year = new_course_section.year
        course_section.section_id = course_section.get_key()

        teacher = Teacher.get_teacher_by_user_id(user.user_id())

        if not teacher:
            errors.append('Unable to add course section. Teacher Entity not found.')
            return None

        course_sections = CourseSectionEntity.get_course_sections_for_user()

        #add new section to list of sections passed in. this should add it by reference and set the collection
        course_sections[course_section.get_key()] = course_section

        teacher.sections = transforms.dumps(course_sections, {})

        teacher.put()

        return section_id

    @classmethod
    def update_course_section(cls, section_id, new_course_section, errors):

        course_sections = CourseSectionEntity.get_course_sections_for_user()

        course_section = CourseSectionEntity()

        course_section.section_id = section_id
        course_section.section_name = new_course_section.name
        course_section.section_description = new_course_section.description
        course_section.is_active = new_course_section.active
        course_section.students = new_course_section.students
        course_section.section_year = new_course_section.year

        course_sections[section_id] = course_section

        user = users.get_current_user()
        if not user:
            errors.append('Unable to update course section. User not found.')
            return False

        teacher = Teacher.get_teacher_by_user_id(user.user_id())

        if not teacher:
            errors.append('Unable to update course section. Teacher Entity not found.')
            return False

        teacher.sections = transforms.dumps(course_sections, {})

        teacher.put()

        return True


    @classmethod
    def get_course_sections_for_user(cls):
        user = users.get_current_user()

        if not user:
            return None

        teacher = Teacher.get_by_email(user.email())

        if not teacher:
            return None

        course_sections = dict()

        if teacher.sections:
            course_sections_decoded = transforms.loads(teacher.sections)

            for course_section_key in course_sections_decoded:
                course_section = CourseSectionEntity(course_sections_decoded[course_section_key])
                course_sections[course_section.section_id] = course_section

        return course_sections

    @classmethod
    def get_course_for_user(cls, key):
        user = users.get_current_user()

        if not user:
            return None

        teacher = Teacher.get_by_email(user.email())

        if not teacher:
            return None

        if teacher.sections:
            course_sections_decoded = transforms.loads(teacher.sections)

            for course_section_key in course_sections_decoded:
                if course_section_key == key:
                    return CourseSectionEntity(course_sections_decoded[course_section_key])


class CourseSectionDTO(object):
    def __init__(self, section_id, data_dict):
        self._id = section_id
        self.dict = data_dict

    @classmethod
    def build(cls, name, description, active, students=None, year=None):
        return CourseSectionDTO(None, {
            'name': name,
            'description': description,
            'active': active,
            'students': students,
            'year': year
        })

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self.dict.get('name')

    @property
    def description(self):
        return self.dict.get('description')

    @property
    def active(self):
        return self.dict.get('active')

    @property
    def students(self):
        return self.dict.get('students')

    @property
    def year(self):
        return self.dict.get('year')

class CourseSectionDAO(BaseJsonDao):
    DTO = CourseSectionDTO
    ENTITY = CourseSectionEntity
    ENTITY_KEY_TYPE = BaseJsonDao.EntityKeyTypeId




