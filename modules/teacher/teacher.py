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

""" Classes and methods to create and manage the Teacher Dashboard.
    Based off of the announcements module, which was created by 
    saifu@google.com.   
"""

__author__ = 'Saifu Angto (saifu@google.com)'
__author__ = 'ehiller@css.edu'
__author__ = 'Ralph Morelli (ram8647@gmail.com)'

import cgi
import datetime
import os
import urllib
import logging

import jinja2

import appengine_config
from common import tags
from common import utils as common_utils
from common import schema_fields
from controllers import utils
from models import resources_display
from models import custom_modules
from models import entities
from models import models
from models import roles
from models import transforms
from models.models import MemcacheManager
from models.models import Student
from modules.teacher import messages
from modules.dashboard import dashboard
from modules.oeditor import oeditor

from google.appengine.ext import db
from google.appengine.api import users

# Our modules classes
from course_entity import CourseSectionEntity
from course_entity import SectionItemRESTHandler
from teacher_entity import TeacherEntity
from teacher_entity import TeacherItemRESTHandler
from teacher_entity import TeacherRights

MODULE_NAME = 'teacher'
MODULE_TITLE = 'Teacher Dashboard'

#Setup paths and directories for templates and resources
RESOURCES_PATH = '/modules/teacher/resources'
TEMPLATES_DIR = os.path.join(
    appengine_config.BUNDLE_ROOT, 'modules', MODULE_NAME, 'templates')

# These are the module's templates.  The first is the teacher's splash page.
TEACHERS_TEMPLATE = os.path.join(TEMPLATES_DIR, 'teacher_dashboard.html')
STUDENT_ROSTER_TEMPLATE = os.path.join(TEMPLATES_DIR, 'student_roster.html')

class TeacherHandlerMixin(object):
    def get_admin_action_url(self, action, key=None):
        args = {'action': action}
        if key:
            args['key'] = key
        return self.canonicalize_url(
            '{}?{}'.format(
                AdminDashboardHandler.URL, urllib.urlencode(args)))

    def get_dashboard_action_url(self, action, key=None):
        args = {'action': action}
        if key:
            args['key'] = key
        return self.canonicalize_url(
            '{}?{}'.format(
                TeacherDashboardHandler.DASHBOARD_URL, urllib.urlencode(args)))

    def format_admin_template(self, items):
        """ Formats the template for the Admin 'Add Teacher' page.

            When clicked the 'Admin: Add Teacher button opens up 
            a list of teachers plus and 'Add Teacher' button.
        """
        template_items = []
        for item in items:
            item = transforms.entity_to_dict(item)
            date = item.get('date')
            if date:
                date = datetime.datetime.combine(
                    date, datetime.time(0, 0, 0, 0))
                item['date'] = (
                    date - datetime.datetime(1970, 1, 1)).total_seconds() * 1000

            # add 'edit' actions
            if TeacherRights.can_edit(self):
                item['edit_action'] = self.get_admin_action_url(
                     AdminDashboardHandler.ADMIN_EDIT_ACTION, key=item['key'])
                item['delete_xsrf_token'] = self.create_xsrf_token(
                    AdminDashboardHandler.ADMIN_DELETE_ACTION)
                item['delete_action'] = self.get_admin_action_url(
                    AdminDashboardHandler.ADMIN_DELETE_ACTION,
                    key=item['key'])

            template_items.append(item)

        output = {}
        output['children'] = template_items

        # Add actions for the 'Add Teacher'
        if TeacherRights.can_edit(self):
            output['add_xsrf_token'] = self.create_xsrf_token(
                AdminDashboardHandler.ADMIN_ADD_ACTION)
            output['add_action'] = self.get_admin_action_url(
                AdminDashboardHandler.ADMIN_ADD_ACTION)

        return output

    def format_dashboard_template(self, sections, user_email):
        """ Formats the template for the main Teacher Dashboard page.

            This is the page that registered teachers will see.  It consists of
            list of the teacher's course sections and buttons to manage the
            sections. 
        """
        template_sections = []
        if sections:
            for section in sections:
                section = transforms.entity_to_dict(section)

                logging.debug('***RAM*** format template section = ' + str(section))

                # Add 'edit' and 'delete' actions to each section that will be displayed

                if section['teacher_email'] == user_email and TeacherRights.can_edit(self):
                    section['edit_action'] = self.get_dashboard_action_url(
                        TeacherDashboardHandler.EDIT_SECTION_ACTION, key=section['key'])

                    section['delete_xsrf_token'] = self.create_xsrf_token(
                        TeacherDashboardHandler.DELETE_SECTION_ACTION)
                    section['delete_action'] = self.get_dashboard_action_url(
                        TeacherDashboardHandler.DELETE_SECTION_ACTION,
                        key=section['key'])
                    template_sections.append(section) 

        output = {}
        output['sections'] = template_sections

        # Add actions for the 'New Section' button
        output['newsection_xsrf_token'] = self.create_xsrf_token(
            TeacherDashboardHandler.ADD_SECTION_ACTION)
        output['add_section'] = self.get_dashboard_action_url(
            TeacherDashboardHandler.ADD_SECTION_ACTION)

        # Add actions of the 'Admin' button -- to add new teachers
        if TeacherRights.can_edit(self):
            output['is_admin'] = True
            output['add_xsrf_token'] = self.create_xsrf_token(
                AdminDashboardHandler.ADMIN_LIST_ACTION)
            output['add_action'] = self.get_admin_action_url(
                AdminDashboardHandler.ADMIN_LIST_ACTION)
        return output

class TeacherDashboardHandler(
        TeacherHandlerMixin, utils.BaseHandler,
        utils.ReflectiveRequestHandler):

    """  Handle all Teacher (non-Admin) functions for the Teacher Dashboard.

         The Teacher functions include creating and deleting course sections,
         adding and removing students from sections, and monitoring student
         performance. The Admin functions consist solely of registering teachers
         and are handled by AdminDashboardHandler.
    """

    # Actions for the various Section functions
    LIST_SECTION_ACTION = 'edit_sections'
    EDIT_SECTION_ACTION = 'edit_section'
    DELETE_SECTION_ACTION = 'delete_section'
    ADD_SECTION_ACTION = 'add_section'
    DISPLAY_ROSTER_ACTION = 'display_roster'

    # The links for Teacher functions
    DASHBOARD_LINK_URL = 'teacher'
    DASHBOARD_URL = '/{}'.format(DASHBOARD_LINK_URL)
    DASHBOARD_LIST_URL = '{}?action={}'.format(DASHBOARD_LINK_URL, LIST_SECTION_ACTION)

    # Not sure what these do?  May be expendable?
    default_action = 'edit_sections'
    get_actions = [default_action, LIST_SECTION_ACTION, EDIT_SECTION_ACTION, ADD_SECTION_ACTION, DISPLAY_ROSTER_ACTION]
    post_actions = [DELETE_SECTION_ACTION]

    def is_registered_teacher(self, user_email):
        """Determines if current user is a registered teacher."""

        items = TeacherEntity.get_teachers()
        items = TeacherRights.apply_rights(self, items)
        for teacher in items:
#            logging.debug('***RAM*** teacher = ' + str(teacher.email))
#            logging.debug('***RAM*** user ' + str(users.User.email(user)))
            if teacher.email == user_email:
                return True
        return False
    
    def _render(self):
        """ Renders the TEACHERS_TEMPLATE by calling super.render(template)

            This assumes that the template's values are in template_value.
        """
        self.template_value['navbar'] = {'teacher': True}
        self.render(TEACHERS_TEMPLATE)

    def _render_roster(self):
        """ Renders the STUDENT_ROSTER_TEMPLATE by calling super.render(template)

            This assumes that the template's values are in template_value.
        """
        self.template_value['navbar'] = {'teacher': True}
        self.render(STUDENT_ROSTER_TEMPLATE)

    def render_page(self, template):
        """ Renders the template that's supplied as an argument."""

        self.template_value['navbar'] = {'teacher': True}
        self.render(template)

    def get_edit_sections(self):
        """ Displays a list of this teacher's sections, using the TEACHERS_TEMPLATE.

            This callback method automatically handles 'edit_sections' actions and must be
            named 'get_edit_sections'.

            This action displays the splash page for the Teacher Dashboard. It
            displays when the user clicks on the navbar 'Teachers' tab. From there
            the Teacher can manage all their sections.   It also contains an
            'Admin: Add Teacher' button, which is visible only to admin users.
            Its action is handled by AdminDashboardHandler.

            The template is injected with a list of this teacher's sections.
        """
        # Make sure the user is a registered teacher
        alerts = []
        disable = False
        user_email = users.get_current_user().email()
        if not self.is_registered_teacher(user_email):
            alerts.append('Access denied. Please see a course admin.')
            disable = True

        sections = CourseSectionEntity.get_sections()
        sections = TeacherRights.apply_rights(self, sections)

        logging.debug('***RAM*** Trace: get_edit_sections')

        # self._render will render the SECTIONS template
        self.template_value['teacher'] = self.format_dashboard_template(sections, user_email)
        self.template_value['teacher_email'] = user_email
        self.template_value['alerts'] = alerts
        self.template_value['disabled'] = disable
        self._render()

    def get_add_section(self):
        """ Shows an editor for a section entity.

            This callback method is triggered when the user clicks on the 
            'Create New Section' button in the Teacher splach page.
        """
        if not TeacherRights.can_add_section(self):
            self.error(401)
            return

        logging.debug('***RAM** get_add_section')
        entity = CourseSectionEntity.make('', '', '', True)
        entity.put()

        self.redirect(self.get_dashboard_action_url(
            self.EDIT_SECTION_ACTION, key=entity.key()))

    def get_edit_section(self):
        """Shows an editor for a section."""

        key = self.request.get('key')

        schema = SectionItemRESTHandler.SCHEMA()

        exit_url = self.canonicalize_url('/{}'.format(self.DASHBOARD_LIST_URL))
        rest_url = self.canonicalize_url('/rest/section/item')
        form_html = oeditor.ObjectEditor.get_html_for(
            self,
            schema.get_json_schema(),
            schema.get_schema_dict(),
            key, rest_url, exit_url,
            delete_method='delete',
            delete_message='Are you sure you want to delete this section?',
            delete_url=self._get_delete_url(
                SectionItemRESTHandler.URL, key, 'section-delete'),
            display_types=schema.get_display_types())

        logging.debug('***RAM** get_edit_section rendering page')
        self.template_value['main_content'] = form_html;
        self._render()

    def post_delete_section(self):
        """Deletes a section."""
        if not TeacherRights.can_delete_section(self):
            self.error(401)
            return

        logging.debug('***RAM** post_delete_section')
        key = self.request.get('key')
        entity = CourseSectionEntity.get(key)
        if entity:
            entity.delete()
        self.redirect('/{}'.format(self.DASHBOARD_LIST_URL))

    def _get_delete_url(self, base_url, key, xsrf_token_name):
        return '%s?%s' % (
            self.canonicalize_url(base_url),
            urllib.urlencode({
                'key': key,
                'xsrf_token': cgi.escape(
                    self.create_xsrf_token(xsrf_token_name)),
            }))

    def get_display_roster(self):
        """Callback method to display the Roster view. 

           This is called when the user clicks on the 'View Roster' button  
           from the main Teacher Dashboard page.  It displays all students 
           in a single course section and their progress in the course.
           Also allows the teacher to manage the section.
        """
        key = self.request.get('key')
        course_section = CourseSectionEntity.get(key)

        # Get a progress tracker for the course
        this_course = self.get_course()
        tracker = this_course.get_progress_tracker()

        # Get this course's units
        units = this_course.get_units()
        units_filtered = filter(lambda x: x.type == 'U', units) #filter out assessments

        # And lessons
        lessons = {}
        for unit in units_filtered:
            unit_lessons = this_course.get_lessons(unit.unit_id)
            unit_lessons_filtered = []
            for lesson in unit_lessons:
                unit_lessons_filtered.append({
                    'title': lesson.title,
                    'unit_id': lesson.unit_id,
                    'lesson_id': lesson.lesson_id
                })
            lessons[unit.unit_id] = unit_lessons_filtered
        
        # Convert to JSON
        lessons = transforms.dumps(lessons, {}) 

        # Get all students in this section 
        if course_section.students:
            section_students = course_section.students.split(',')
        else:
            section_students = []
            logging.debug('***RAM*** section Students : ' + str(section_students))
        students = []
        if section_students and len(section_students) > 0:
            for student in section_students:
                this_student = Student.get_first_by_email(student)[0]   # returns a tuple
                # Guard against email for non-existent student
                if this_student:
                    logging.debug('***RAM*** student = ' + str(this_student))
                    temp_student = {}
                    units_completed = tracker.get_unit_percent_complete(this_student)
                    progress = 0
                    for value in units_completed.values():
                        progress += value
                
                    temp_student['unit_completion'] = units_completed
                    temp_student['course_progress'] = str(round(progress / len(units_completed) * 100,2))
                    temp_student['email'] = student
                    temp_student['name'] = this_student.name
                    students.append(temp_student)

        logging.debug('***RAM*** Students : ' + str(students))

        user_email = users.get_current_user().email()
        self.template_value['section'] = { 'key': key, 'teacher': user_email, 'name' : course_section.name, 'description' : course_section.description }
        self.template_value['units'] = units_filtered
        self.template_value['lessons'] = lessons
        self.template_value['students'] = students

        self._render_roster()
#         #need to get progress values for ALL students since we show completion for every student
#         if course_section.students and len(course_section.students) > 0:
#             #course_section.students = sorted(course_section.students.values(), key=lambda k: (k['name']))
#             for student in course_section.students.values():
#                 this_student = Teacher.get_student_by_email(student['email'])
#                 temp_student = {}

#                 temp_student['unit_completion'] = teacher_parsers.StudentProgressTracker.get_unit_completion(
#                     this_student, self.get_course())
#                 temp_student['course_completion'] = teacher_parsers.StudentProgressTracker.get_overall_progress(
#                     this_student, self.get_course())
#                 temp_student['detailed_course_completion'] = teacher_parsers.StudentProgressTracker.get_detailed_progress(
#                     this_student, self.get_course())
#                 temp_student['email'] = student['email']
#                 temp_student['name'] = student['name']

#                 students[student['email']] = temp_student

#         course_section.students = students

#         #passing in students as JSON so JavaScript can handle updating completion values easier
#         template_values['students_json'] = transforms.dumps(course_section.students, {})
#         template_values['namespace'] = self.get_course()._namespace.replace('ns_', '')

#         if course_section:
#             template_values['section'] = course_section

#         #render student_list.html for Roster view
#         main_content = self.get_template(
#             'student_list.html', [TEMPLATES_DIR]).render(template_values)

#         #DashboardHandler renders the page -- that won't work 
#         self.render_page({
#             'page_title': self.format_title('Student List'),
#             'main_content': jinja2.utils.Markup(main_content)})


class AdminDashboardHandler(TeacherHandlerMixin, dashboard.DashboardHandler):

    """ Handler for all Admin functions, which basically consists of giving teachers
        access to the Teacher Dashboard.

        This is a subclass of DashboardHandler, so it comes with functionality that
        is available to other Handlers, mainly in how pages are rendered.
        DashboardHandler has a render_page method that is not available in other
        handlers.
    """

    # The various Admin Actions
    ADMIN_LIST_ACTION = 'edit_teachers'
    ADMIN_EDIT_ACTION = 'edit_teacher'
    ADMIN_DELETE_ACTION = 'delete_teacher'
    ADMIN_ADD_ACTION = 'add_teacher'

    # Not sure what these do?
    get_actions = [ADMIN_EDIT_ACTION, ADMIN_LIST_ACTION]
    post_actions = [ADMIN_ADD_ACTION, ADMIN_DELETE_ACTION]

    ADMIN_LINK_URL = 'mcsp_admin'
    URL = '/{}'.format(ADMIN_LINK_URL)
    ADMIN_LIST_URL = '{}?action={}'.format(ADMIN_LINK_URL, ADMIN_LIST_ACTION)

    @classmethod
    def get_child_routes(cls):

        """ Add child handlers for REST. The REST handlers perform
            retrieve and store teachers, sections, and other data
            used by the Teacher Dashboard.
        """

        logging.debug('***RAM** get_child_routes')
        return [
            (TeacherItemRESTHandler.URL, TeacherItemRESTHandler),
            (SectionItemRESTHandler.URL, SectionItemRESTHandler)
            ]

    def get_edit_teachers(self):

        """ Displays a list of registered teachers.

            This is the splash page for Admin users of Teacher Dashboard.
            It is reached by clicking the 'Admin: Add Teacher' button in
            the Teacher Dashboard splash page.  From this page Admins can
            perform all tasks associated with registering teachers.
        """

        items = TeacherEntity.get_teachers()
        items = TeacherRights.apply_rights(self, items)

        logging.debug('***RAM**  Trace: get_edit_teachers')
        main_content = self.get_template(
            'mcsp_admin_dashboard.html', [TEMPLATES_DIR]).render({
                'teachers': self.format_admin_template(items),
            })

        self.render_page({
            'page_title': self.format_title('Teachers'),
            'main_content': jinja2.utils.Markup(main_content)})

    def get_edit_teacher(self):
        """Shows an editor for a teacher."""

        key = self.request.get('key')

        schema = TeacherItemRESTHandler.SCHEMA()

        exit_url = self.canonicalize_url('/{}'.format(self.ADMIN_LIST_URL))
        rest_url = self.canonicalize_url('/rest/teacher/item')
        form_html = oeditor.ObjectEditor.get_html_for(
            self,
            schema.get_json_schema(),
            schema.get_schema_dict(),
            key, rest_url, exit_url,
            delete_method='delete',
            delete_message='Are you sure you want to delete this teacher?',
            delete_url=self._get_delete_url(
                TeacherItemRESTHandler.URL, key, 'teacher-delete'),
            display_types=schema.get_display_types())

        logging.debug('***RAM** get_edit_teacher rendering page')
        self.render_page({
            'main_content': form_html,
            'page_title': 'Edit Teacher',
        }, in_action=self.ADMIN_LIST_ACTION)

    def post_delete_teacher(self):
        """Deletes an teacher."""
        if not TeacherRights.can_delete(self):
            self.error(401)
            return

        logging.debug('***RAM** post_delete_teacher')
        key = self.request.get('key')
        entity = TeacherEntity.get(key)
        if entity:
            entity.delete()
        self.redirect('/{}'.format(self.ADMIN_LIST_URL))

    def post_add_teacher(self):
        """Adds a new teacher and redirects to an editor for it."""
        if not TeacherRights.can_add(self):
            self.error(401)
            return

        logging.debug('***RAM** post_add_teacher')
        entity = TeacherEntity.make('', '', '')
        entity.put()

        self.redirect(self.get_admin_action_url(
            self.ADMIN_EDIT_ACTION, key=entity.key()))

    def _get_delete_url(self, base_url, key, xsrf_token_name):
        return '%s?%s' % (
            self.canonicalize_url(base_url),
            urllib.urlencode({
                'key': key,
                'xsrf_token': cgi.escape(
                    self.create_xsrf_token(xsrf_token_name)),
            }))



def notify_module_enabled():
    """Handles things after module has been enabled."""


custom_module = None


def register_module():
    """Registers this module in the registry."""

    handlers = [
        (AdminDashboardHandler.URL, AdminDashboardHandler),
        (TeacherDashboardHandler.DASHBOARD_URL, TeacherDashboardHandler)
    ]

    global_routes = [
    ]

    dashboard.DashboardHandler.add_sub_nav_mapping(
        'analytics', MODULE_NAME, MODULE_TITLE,
        action=AdminDashboardHandler.ADMIN_LIST_ACTION,
        href=AdminDashboardHandler.ADMIN_LIST_URL,
        placement=1000, sub_group_name='pinned')

    global custom_module  # pylint: disable=global-statement
    custom_module = custom_modules.Module(
        MODULE_TITLE,
        'A set of pages for managing course teachers.',
        global_routes, handlers,
        notify_module_enabled=notify_module_enabled)

    return custom_module
