__author__ = 'ehiller@css.edu'

import teacher_entity

from google.appengine.api import users

from common import crypto

from models import transforms
from models.models import Student

from controllers.utils import BaseRESTHandler

from common.resource import AbstractResourceHandler
from common import schema_fields

import teacher_parsers


class ActivityScoreRestHandler(BaseRESTHandler):
    """REST handler to manage retrieving activity scores.

    Note:
        Inherits from BaseRESTHandler.

    Attributes:
        SCHEMA_VERSIONS (int): Current version of REST handler
        URL (str): Path to REST handler
        XSRF_TOKEN (str): Token used for xsrf security functions.

    """

    XSRF_TOKEN = 'activity-scores-handler'
    SCHEMA_VERSIONS = ['1']

    URL = '/rest/modules/teacher_dashboard/activity_scores'

    @classmethod
    def get_schema(cls):
        #TODO: implement a schema if necessary, not sure if needed since we aren't putting any data
        pass

    def get(self):
        """Get activity scores."""
        request = transforms.loads(self.request.get('request'))
        payload = transforms.loads(request.get('payload'))
        errors = []

        students = payload['students']
        force_refresh = payload['forceRefresh']
        course = self.get_course()

        temp_students = []
        for student in students:
            if '@' in student:
                temp_students.append(Student.get_by_email(student).user_id)

        if len(temp_students) > 0:
            students = temp_students

        if len(students) > 0:
            scores = teacher_parsers.ActivityScoreParser.get_activity_scores(students, course, force_refresh)
        else:
            errors.append('An error occurred retrieving activity scores. Contact your course administrator.')
            self.validation_error('\n'.join(errors))
            return

        payload_dict = {
            'scores': scores['scores'],
            'dateCached': scores['date'].strftime("%B %d, %Y %H:%M:%S")
        }

        transforms.send_json_response(
            self, 200, '', payload_dict=payload_dict,
            xsrf_token=crypto.XsrfTokenManager.create_xsrf_token(
                self.XSRF_TOKEN))

class StudentProgressRestHandler(BaseRESTHandler):
    """REST handler to manage retrieving student progress.

    Note:
        Inherits from BaseRESTHandler.

    Attributes:
        SCHEMA_VERSIONS (int): Current version of REST handler
        URL (str): Path to REST handler
        XSRF_TOKEN (str): Token used for xsrf security functions.

    """

    XSRF_TOKEN = 'student-progress-handler'
    SCHEMA_VERSIONS = ['1']

    URL = '/rest/modules/teacher_dashboard/student_progress'

    @classmethod
    def get_schema(cls):
        #TODO: implement a schema if necessary, not sure if needed since we aren't putting any data
        pass

    def get(self):
        """Get a students progress."""

        #teachers aren't course admins, so we probably shouldn't check for that
        # if not roles.Roles.is_course_admin(self.app_context):
        #     transforms.send_json_response(self, 401, 'Access denied.', {})
        #     return

        key = self.request.get('student')
        errors = []

        student = Student.get_by_email(key.strip())
        course = self.get_course()

        if student:
            units = teacher_parsers.StudentProgressTracker.get_detailed_progress(student, course)
        else:
            errors.append('An error occurred retrieving student data. Contact your course administrator.')
            self.validation_error('\n'.join(errors))
            return

        payload_dict = {
            'units': units,
            'student_name': student.name,
            'student_email': student.email
        }

        transforms.send_json_response(
            self, 200, '', payload_dict=payload_dict,
            xsrf_token=crypto.XsrfTokenManager.create_xsrf_token(
                self.XSRF_TOKEN))

class CourseSectionRestHandler(BaseRESTHandler):
    """REST handler to manage retrieving and updating course sections.

    Note:
        Inherits from BaseRESTHandler.

    Attributes:
        SCHEMA_VERSIONS (int): Current version of REST handler
        URL (str): Path to REST handler
        XSRF_TOKEN (str): Token used for xsrf security functions.

    """

    XSRF_TOKEN = 'section-handler'
    SCHEMA_VERSIONS = ['1']

    URL = '/rest/modules/teacher_dashboard/section'

    @classmethod
    def get_schema(cls):
        """Return the schema for the section editor."""
        return ResourceSection.get_schema(course=None, key=None)

    def get(self):
        """Get a section."""

        key = self.request.get('key')

        course_sections = teacher_entity.CourseSectionEntity.get_course_sections_for_user()

        if course_sections is not None:
            sorted_course_sections = sorted(course_sections.values(), key=lambda k: (k.section_year,
                                                                                 k.section_name.lower()))
        else:
            sorted_course_sections = {}

        payload_dict = {
            'section_list': sorted_course_sections
        }

        if key:
            payload_dict['section'] = teacher_entity.CourseSectionEntity.get_course_for_user(str(key))

        transforms.send_json_response(
            self, 200, '', payload_dict=payload_dict,
            xsrf_token=crypto.XsrfTokenManager.create_xsrf_token(
                self.XSRF_TOKEN))

    def delete(self):
        """Deletes a section."""
        pass

    def put(self):
        """Inserts or updates a course section."""
        request = transforms.loads(self.request.get('request'))
        key = request.get('key')

        if not self.assert_xsrf_token_or_fail(
                request, self.XSRF_TOKEN, {}):
            return

        payload = request.get('payload')
        json_dict = transforms.loads(payload)
        python_dict = transforms.json_to_dict(
            json_dict, self.get_schema().get_json_schema_dict(),
            permit_none_values=True)

        version = python_dict.get('version')
        if version not in self.SCHEMA_VERSIONS:
            self.validation_error('Version %s not supported.' % version)
            return

        errors = []

        teacher = teacher_entity.Teacher.get_by_email(users.get_current_user().email())

        if not teacher:
            errors.append('Unable to save changes. Teacher is not registered. Please contact a course admin.')
            self.validation_error('\n'.join(errors))
            return

        if not teacher.is_active:
            errors.append('Unable to save changes. Teacher account is inactive.')
            self.validation_error('\n'.join(errors))
            return

        if key:
            key_after_save = key
            new_course_section = teacher_entity.CourseSectionEntity.get_course_for_user(key)

            students = new_course_section.students or {}
            emails = ""
            if 'students' in python_dict and python_dict['students'] is not None:
                emails = python_dict['students']['emails'].split(',')
            for email in emails:
                clean_email = email.strip().replace('\n', '').replace('\r', '')
                student = Student.get_by_email(clean_email)
                if student:
                    if python_dict['students']['action'] == 'insert':
                        student_info = {}
                        student_info['email'] = clean_email
                        student_info['name'] = student.name
                        student_info['user_id'] = student.user_id
                        students[student.user_id] = student_info
                    else:
                        students.pop(student.user_id, None)
                else:
                    errors.append('Unable to find student with email: ' + clean_email)

            sorted_students = sorted(students.values(), key=lambda k: (k['name']))

            if python_dict.get('name') != None:
                new_course_section.section_name = python_dict.get('name')
            if python_dict.get('active') != None:
                new_course_section.is_active = python_dict.get('active')
            if python_dict.get('description') != None:
                new_course_section.section_description = python_dict.get('description')
            if python_dict.get('year') != None:
                new_course_section.section_year = python_dict.get('year')

            course_section = teacher_entity.CourseSectionDTO.build(
                new_course_section.section_name, new_course_section.section_description,
                new_course_section.is_active, students, new_course_section.section_year)
            teacher_entity.CourseSectionEntity.update_course_section(key, course_section, errors)
        else:
            course_section = teacher_entity.CourseSectionDTO.build(
                python_dict.get('name'), python_dict.get('description'), python_dict.get('active'), {},
                python_dict.get('year'))
            key_after_save = teacher_entity.CourseSectionEntity.add_new_course_section(key, course_section, errors)

        if errors:
            self.validation_error('\n'.join(errors), key=key_after_save)
            return

        section = teacher_entity.CourseSectionEntity.get_course_for_user(key_after_save)
        if section:
            section.students = sorted_students
            if section.students and len(section.students) > 0:
                for student in section.students:
                    student['unit_completion'] = teacher_parsers.StudentProgressTracker.get_unit_completion(
                        Student.get_by_email(
                        student[
                        'email']), self.get_course())
                    student['course_completion'] = teacher_parsers.StudentProgressTracker.get_overall_progress(
                        Student.get_by_email(
                        student[
                        'email']), self.get_course())
                    student['detailed_course_completion'] = \
                        teacher_parsers.StudentProgressTracker.get_detailed_progress(
                        Student.get_by_email(student['email']), self.get_course())

        course_sections = teacher_entity.CourseSectionEntity.get_course_sections_for_user()

        if course_sections is not None:
            sorted_course_sections = sorted(course_sections.values(), key=lambda k: (k.section_year,
                                                                                 k.section_name.lower()))
        else:
            sorted_course_sections = {}

        payload_dict = {
            'key': key_after_save,
            'section': section,
            'section_list': sorted_course_sections
        }

        transforms.send_json_response(
            self, 200, 'Saved.', payload_dict)

class ResourceSection(AbstractResourceHandler):
    """Definition for the course section resource.

    Note:
        Inherits from AbstractResourceHandler.

    Attributes:
        TYPE (int): entity for resource

    """

    TYPE = 'course_section'

    @classmethod
    def get_resource(cls, course, key):
        """Loads a course section."""
        return teacher_entity.CourseSectionDAO.load(key)

    @classmethod
    def get_resource_title(cls, rsrc):
        """Returns course name."""
        return rsrc.name

    @classmethod
    def get_schema(cls, course, key):
        """Returns a schema definition of a section."""
        schema = schema_fields.FieldRegistry(
            'Section', description='section')
        schema.add_property(schema_fields.SchemaField(
            'version', '', 'string', optional=True, hidden=True))
        schema.add_property(schema_fields.SchemaField(
            'name', 'Name', 'string', optional=True))
        schema.add_property(schema_fields.SchemaField(
            'description', 'Description', 'text', optional=True))
        schema.add_property(schema_fields.SchemaField(
            'active', 'Active', 'boolean', optional=True))
        schema.add_property(schema_fields.SchemaField(
            'students', 'Students', 'string', optional=True))
        schema.add_property(schema_fields.SchemaField(
            'year', 'Year', 'string', optional=True))
        return schema

    @classmethod
    def get_data_dict(cls, course, key):
        return cls.get_resource(course, key).dict

    @classmethod
    def get_view_url(cls, rsrc):
        return None

    @classmethod
    def get_edit_url(cls, key):
        return None

