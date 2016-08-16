__author__ = 'ehiller@css.edu'


# Module to support custom teacher views in CourseBuilder dashboard
# Views include:
#       Section Roster - list of students in section
#       Sections - list of sections for current user
#       Student Dashboard - view of a single student's performance in the course
#       Teacher Workspace - teacher registration and list of all registered teachers

import jinja2
import os
import collections

import appengine_config

from common import tags
from common import crypto

from models import custom_modules
from models import roles
from models import transforms
from models.models import Student

#since we are extending the dashboard, probably want to include dashboard stuff
from modules.dashboard import dashboard
#from modules.dashboard import tabs

#import our own modules
import teacher_entity
import teacher_rest_handlers
import teacher_parsers

from teacher_entity import Teacher

#Setup paths and directories for templates and resources
RESOURCES_PATH = '/modules/teacher_dashboard/resources'

TEMPLATES_DIR = os.path.join(
    appengine_config.BUNDLE_ROOT, 'modules', 'teacher_dashboard', 'templates')

#setup permissions that will be registered with the dashboard
ACCESS_ASSETS_PERMISSION = 'can_access_assets'
ACCESS_ASSETS_PERMISSION_DESCRIPTION = 'Can access the Assets Dashboard'

ACCESS_SETTINGS_PERMISSION = 'can_access_settings'
ACCESS_SETTINGS_PERMISSION_DESCRIPTION = 'Can access the Settings Dashboard'

ACCESS_ROLES_PERMISSION = 'can_access_roles'
ACCESS_ROLES_PERMISSION_DESCRIPTION = 'Can access the Roles Dashboard'

ACCESS_ANALYTICS_PERMISSION = 'can_access_analytics'
ACCESS_ANALYTICS_PERMISSION_DESCRIPTION = 'Can access the Analytics Dashboard'

ACCESS_SEARCH_PERMISSION = 'can_access_search'
ACCESS_SEARCH_PERMISSION_DESCRIPTION = 'Can access the Search Dashboard'

ACCESS_PEERREVIEW_PERMISSION = 'can_access_peer_review'
ACCESS_PEERREVIEW_PERMISSION_DESCRIPTION = 'Can access the Peer Review Dashboard'

ACCESS_SKILLMAP_PERMISSION = 'can_access_skill_map'
ACCESS_SKILLMAP_PERMISSION_DESCRIPTION = 'Can access the Skill Map Dashboard'

ACCESS_TEACHER_DASHBOARD_PERMISSION = 'can_access_teacher_dashboard'
ACCESS_TEACHER_DASHBOARD_PERMISSION_DESCRIPTION = 'Can access the Teacher Dashboard'

#setup custom module for, needs to be referenced later
custom_module = None

class TeacherHandler(dashboard.DashboardHandler):
    """Handler for everything under the Teacher tab in the CourseBuilder dashboard.

    Note:
        Inherits from the DashboardHandler, makes use of many of those functions to
        integrate with existing dashboard.

    Attributes:
        ACTION (str): Value used to handler navigation in the dashboard, top level label.
        DEFAULT_TAB (str): Default sub-navigation value.
        URL (str): Path to module from working directory.
        XSRF_TOKEN_NAME (str): Token used for xsrf security functions.

    """

    ACTION = 'teacher_dashboard'
    DEFAULT_TAB = 'sections'

    URL = '/modules/teacher_dashboard'

    XSRF_TOKEN_NAME = ''

    # Dictionary that maps external permissions to their descriptions
    _external_permissions = {}

    @classmethod
    def add_external_permission(cls, permission_name,
                                           permission_description):
        """Adds extra permissions that will be registered by the Dashboard."""
        cls._external_permissions[permission_name] = permission_description

    def get_teacher_dashboard(self):
        """Process navigation requests sent to teacher handler. Routers to appropriate function."""

        in_tab = self.request.get('tab') or self.DEFAULT_TAB
        tab_action = self.request.get('tab_action') or None #defined a secondary tab property so I can go load a
                                                            # separate view in the same tab

        if in_tab == 'sections':
            if tab_action == 'roster':
                return self.get_roster()
            else:
                return self.get_sections()
        elif in_tab == 'teacher_reg':
            return self.get_teacher_reg()
        elif in_tab == 'student_detail':
            return self.get_student_dashboard()

    def get_sections(self):
        """Renders Sections view. Javascript handles getting course sections and building the view"""
        template_values = {}
        template_values['namespace'] = self.get_course()._namespace.replace('ns_', '')

        main_content = self.get_template(
            'teacher_sections.html', [TEMPLATES_DIR]).render(template_values)

        self.render_page({
            'page_title': self.format_title('Sections'),
            'main_content': jinja2.utils.Markup(main_content)})

    def get_student_dashboard(self):
        """Renders Student Dashboard view.

           Also gets ALL students in ALL course sections for the registered user to
           build a jQuery autocomplete dropdown on the view.
        """

        student_email = self.request.get('student') or None #email will be in the request if opened from student list
                                                            # view, otherwise it will be None

        #need to go through every course section for the current user and get all unique students
        students = []
        course_sections = teacher_entity.CourseSectionEntity.get_course_sections_for_user()
        if course_sections and len(course_sections) > 0:
            for course_section in course_sections.values():
                if course_section.students and len(course_section.students) > 0:
                    for student_in_section in course_section.students.values():
                        if not any(x['user_id'] == student_in_section['user_id'] for x in students):
                            students.append(student_in_section)

        #check to see if we have a student and if we need to get detailed progress
        student = None
        if student_email:
            student = Teacher.get_student_by_email(student_email)
#            student = Student.get_by_email(student_email)

        if (student):
            course = self.get_course()
            units = teacher_parsers.StudentProgressTracker.get_detailed_progress(student, course)
            scores = teacher_parsers.ActivityScoreParser.get_activity_scores([student.user_id], course)
        else:
            units = None
            scores = None

        #render the template for the student dashboard view
        main_content = self.get_template(
            'student_detailed_progress.html', [TEMPLATES_DIR]).render(
                {
                    'units': units, #unit completion
                    'student': student, #course defined student object, need email and name
                    'students': students, #list of students, names and emails, from a course section student list
                    'scores': scores
                })

        #call DashboardHandler function to render the page
        self.render_page({
            'page_title': self.format_title('Student Dashboard'),
            'main_content': jinja2.utils.Markup(main_content)
        })


    def get_roster(self):
        """Renders the Roster view. Displays all students in a single course section

           Also allows user to add students to a course section
        """

        template_values = {}
        template_values['add_student_xsrf_token'] = crypto.XsrfTokenManager.create_xsrf_token(
            teacher_rest_handlers.CourseSectionRestHandler.XSRF_TOKEN)

        #need list of units and lessons for select elements that determine which progress value to display
        #need a list of units, need the titles, unit ids, types
        units = self.get_course().get_units()
        units_filtered = filter(lambda x: x.type == 'U', units) #filter out assessments
        template_values['units'] = units_filtered

        #need to get lessons, but only for units that aren't assessments
        lessons = {}
        for unit in units_filtered:
            unit_lessons = self.get_course().get_lessons(unit.unit_id)
            unit_lessons_filtered = []
            for lesson in unit_lessons:
                unit_lessons_filtered.append({
                    'title': lesson.title,
                    'unit_id': lesson.unit_id,
                    'lesson_id': lesson.lesson_id
                })
            lessons[unit.unit_id] = unit_lessons_filtered
        template_values['lessons'] = transforms.dumps(lessons, {}) #passing in JSON to template so it can be used
                                                                    # in JavaScript

        course_section_id = self.request.get('section')

        course_section = teacher_entity.CourseSectionEntity.get_course_for_user(course_section_id)
        students = {}

        #need to get progress values for ALL students since we show completion for every student
        if course_section.students and len(course_section.students) > 0:
            #course_section.students = sorted(course_section.students.values(), key=lambda k: (k['name']))
            for student in course_section.students.values():
                this_student = Teacher.get_student_by_email(student['email'])
                temp_student = {}

                temp_student['unit_completion'] = teacher_parsers.StudentProgressTracker.get_unit_completion(
                    this_student, self.get_course())
##                    Student.get_by_email(
#                     student[
#                     'email']), self.get_course())
                temp_student['course_completion'] = teacher_parsers.StudentProgressTracker.get_overall_progress(
                    this_student, self.get_course())
#                     Student.get_by_email(student[
#                     'email']), self.get_course())
                temp_student['detailed_course_completion'] = teacher_parsers.StudentProgressTracker.get_detailed_progress(
                    this_student, self.get_course())
#                    Student.get_by_email(student['email']), self.get_course())
                temp_student['email'] = student['email']
                temp_student['name'] = student['name']

                students[student['email']] = temp_student

        course_section.students = students

        #passing in students as JSON so JavaScript can handle updating completion values easier
        template_values['students_json'] = transforms.dumps(course_section.students, {})
        template_values['namespace'] = self.get_course()._namespace.replace('ns_', '')

        if course_section:
            template_values['section'] = course_section

        #render student_list.html for Roster view
        main_content = self.get_template(
            'student_list.html', [TEMPLATES_DIR]).render(template_values)

        #DashboardHandler renders the page
        self.render_page({
            'page_title': self.format_title('Student List'),
            'main_content': jinja2.utils.Markup(main_content)})


    def get_teacher_reg(self):
        """Renders Teacher Workspace view. Displays form to add or update a teacher

           Also displays all registered teachers.
        """

        alerts = []
        disable_form = False
  
        if not roles.Roles.is_course_admin(self.app_context):
            alerts.append('Access denied. Please contact a course admin.')
            disable_form = True

        template_values = {}
        template_values['teacher_reg_xsrf_token'] = self.create_xsrf_token('teacher_reg')

        template_values['teachers'] = teacher_entity.Teacher.get_all_teachers_for_course()
        template_values['alert_messages'] = alerts
        template_values['disable'] = disable_form
        template_values['action'] = self.get_action_url('teacher_reg')

        main_content = self.get_template(
            'teacher_registration.html', [TEMPLATES_DIR]).render(template_values)

        self.render_page({
            'page_title': self.format_title('Teacher Registration'),
            'main_content': jinja2.utils.Markup(main_content)})

    @classmethod
    def post_teacher_reg(cls, handler):
        """Handles form submit for teacher registration"""

        #get values entered on form
        email = handler.request.get('email').strip()
        school = handler.request.get('school')

        #getting checkbox value is a little weird, might look different depending on browser
        active = handler.request.get('active-teacher')
        if active == 'on' or len(active) > 0:
            active = True
        else:
            active = False

        #keep track of any errors we might want to pass back to the UI
        alerts = []

        if email == '':
            template_values = {}
            template_values['teacher_reg_xsrf_token'] = handler.create_xsrf_token('teacher_reg')
            alerts = []
            alerts.append('Teacher email cannot be blank.')

            #DashboardHandler renders the page
            template_values['alert_messages'] = '\n'.join(alerts)
            template_values['teachers'] = teacher_entity.Teacher.get_all_teachers_for_course()
            template_values['teacher_reg_xsrf_token'] = handler.create_xsrf_token('teacher_reg')
            main_content = handler.get_template(
                'teacher_registration.html', [TEMPLATES_DIR]).render(template_values)

            handler.render_page({
                'page_title': handler.format_title('Teacher Dashboard'),
                'main_content': jinja2.utils.Markup(main_content)
                },
                'teacher_dashboard'
            )

        #check to see if a teacher already exists
        teacher = teacher_entity.Teacher.get_by_email(email)

        if teacher:
            template_values = {}

            template_values['teacher_reg_xsrf_token'] = handler.create_xsrf_token('teacher_reg')

            sections = {}

            #don't let the teacher be deactivated if they have active courses
            can_inactivate = True
            if active == False:
                if teacher.sections:
                    course_sections_decoded = transforms.loads(teacher.sections)

                    for course_section_key in course_sections_decoded:
                        course_section = teacher_entity.CourseSectionEntity(course_sections_decoded[course_section_key])
                        sections[course_section.section_id] = course_section

                    for section in sections.values():
                        if section.is_active:
                            can_inactivate = False

            #let user know if they can't deactivate, but only if they are trying to deactivate the teacher
            if not can_inactivate and not active:
                alerts.append('Cannot deactivate teacher. Teacher still has active courses')

            #go for the update if all is good
            if can_inactivate:
                teacher_entity.Teacher.update_teacher_for_user(email, school, active, '', alerts)

            #let user know all is well if save was successful
            if len(alerts) == 0:
                alerts.append('Teacher was successfully updated')

            #render teacher_registration.html for view, pass alerts in
            template_values['alert_messages'] = '\n'.join(alerts)
            template_values['teachers'] = teacher_entity.Teacher.get_all_teachers_for_course()
            template_values['teacher_reg_xsrf_token'] = handler.create_xsrf_token('teacher_reg')
            main_content = handler.get_template(
                'teacher_registration.html', [TEMPLATES_DIR]).render(template_values)

            #DashboardHandler renders the page
            handler.render_page({
                'page_title': handler.format_title('Teacher Dashboard'),
                'main_content': jinja2.utils.Markup(main_content)
                },
                'teacher_dashboard'
            )
        else:
            #go for it if teacher doesn't already exist
            teacher_entity.Teacher.add_new_teacher_for_user(email, school, '', alerts)

            template_values = {}

            template_values['alert_messages'] = '\n'.join(alerts)
            template_values['teachers'] = teacher_entity.Teacher.get_all_teachers_for_course()
            template_values['teacher_reg_xsrf_token'] = handler.create_xsrf_token('teacher_reg')
            main_content = handler.get_template(
                'teacher_registration.html', [TEMPLATES_DIR]).render(template_values)

            #DashboardHandler renders the page
            handler.render_page({
                'page_title': handler.format_title('Teacher Dashboard'),
                'main_content': jinja2.utils.Markup(main_content)
                },
                'teacher_dashboard'
            )


def notify_module_enabled():
    """Handles things after module has been enabled."""

    def get_action(handler):
        """Redirects to teacher_dashboard."""
        handler.redirect('/modules/teacher_dashboard?action=teacher_dashboard&tab=%s' % handler.request.get('tab') or
                         TeacherHandler.DEFAULT_TAB)
    def post_action(handler):
        TeacherHandler.post_teacher_reg(handler)

    dashboard.DashboardHandler.add_nav_mapping(TeacherHandler.ACTION, 'Teacher')

    dashboard.DashboardHandler.add_sub_nav_mapping(TeacherHandler.ACTION, 'help', 'Documentation', 
           href='https://docs.google.com/document/d/1XKGfVl_tQDGF0JPQFKh-PKiVKkn5Qu3LOZEJEzpjoaY', target='_blank')
    dashboard.DashboardHandler.add_sub_nav_mapping(TeacherHandler.ACTION, 'sections', 'Sections', href='dashboard?action=teacher_dashboard&tab=')
    dashboard.DashboardHandler.add_sub_nav_mapping(TeacherHandler.ACTION, 'student_detail', 'Students', href='dashboard?action=teacher_dashboard&tab=student_detail' )
    dashboard.DashboardHandler.add_sub_nav_mapping(TeacherHandler.ACTION, 'teacher_reg', 'Teachers', href='dashboard?action=teacher_dashboard&tab=teacher_reg')

    dashboard.DashboardHandler.get_actions.append('teacher_dashboard')
    setattr(dashboard.DashboardHandler, 'get_teacher_dashboard', get_action)

    #add post actions
    dashboard.DashboardHandler.add_custom_post_action('teacher_reg', post_action)
    setattr(dashboard.DashboardHandler, 'post_teacher_reg', post_action)

    #add permissions for the dashboard sections
    TeacherHandler.add_external_permission(
        ACCESS_ASSETS_PERMISSION, ACCESS_ASSETS_PERMISSION_DESCRIPTION)
    TeacherHandler.add_external_permission(
        ACCESS_SETTINGS_PERMISSION, ACCESS_SETTINGS_PERMISSION_DESCRIPTION)
    TeacherHandler.add_external_permission(
        ACCESS_ROLES_PERMISSION, ACCESS_ROLES_PERMISSION_DESCRIPTION)
    TeacherHandler.add_external_permission(
        ACCESS_ANALYTICS_PERMISSION, ACCESS_ANALYTICS_PERMISSION_DESCRIPTION)
    TeacherHandler.add_external_permission(
        ACCESS_SEARCH_PERMISSION, ACCESS_SEARCH_PERMISSION_DESCRIPTION)
    TeacherHandler.add_external_permission(
        ACCESS_PEERREVIEW_PERMISSION, ACCESS_PEERREVIEW_PERMISSION_DESCRIPTION)
    TeacherHandler.add_external_permission(
        ACCESS_SKILLMAP_PERMISSION, ACCESS_SKILLMAP_PERMISSION_DESCRIPTION)
    TeacherHandler.add_external_permission(
        ACCESS_TEACHER_DASHBOARD_PERMISSION, ACCESS_TEACHER_DASHBOARD_PERMISSION_DESCRIPTION)

    #map permissions to actions
    dashboard.DashboardHandler.map_get_action_to_permission(str(TeacherHandler.ACTION), custom_module, ACCESS_TEACHER_DASHBOARD_PERMISSION)

    dashboard.DashboardHandler.EXTRA_JS_HREF_LIST.append('/modules/teacher_dashboard/resources/js/popup.js')
    dashboard.DashboardHandler.EXTRA_JS_HREF_LIST.append('/modules/teacher_dashboard/resources/js/course_section_analytics.js')
    dashboard.DashboardHandler.EXTRA_JS_HREF_LIST.append('/modules/teacher_dashboard/resources/js/activity_score_manager.js')
    dashboard.DashboardHandler.EXTRA_JS_HREF_LIST.append('/modules/teacher_dashboard/resources/js/student_list_table_manager')
    dashboard.DashboardHandler.EXTRA_JS_HREF_LIST.append('/modules/teacher_dashboard/resources/js/student_list_table_rebuild_manager.js')
    dashboard.DashboardHandler.EXTRA_JS_HREF_LIST.append('/modules/teacher_dashboard/resources/js/activity_score_table_manager.js')
    dashboard.DashboardHandler.EXTRA_JS_HREF_LIST.append('/modules/teacher_dashboard/resources/js/student_score_manager.js')

    dashboard.DashboardHandler.EXTRA_CSS_HREF_LIST.append('/modules/teacher_dashboard/resources/css/student_list.css')

    transforms.CUSTOM_JSON_ENCODERS.append(teacher_entity.CourseSectionEntity.json_encoder)


def register_module():
    """Registers this module in the registry."""

    global_routes = [
        (os.path.join(RESOURCES_PATH, 'js', '.*'), tags.JQueryHandler),
        (os.path.join(RESOURCES_PATH, '.*'), tags.ResourcesHandler),
        (RESOURCES_PATH + '/js/popup.js', tags.IifeHandler),
        (RESOURCES_PATH + '/js/course_section_analytics.js', tags.IifeHandler),
        (RESOURCES_PATH + '/js/activity_score_manager.js', tags.IifeHandler),
        (RESOURCES_PATH + '/js/student_list_table_manager', tags.IifeHandler),
        (RESOURCES_PATH + '/js/student_list_table_rebuild_manager.js', tags.IifeHandler),
        (RESOURCES_PATH + '/js/activity_score_table_manager.js', tags.IifeHandler),
        (RESOURCES_PATH + '/js/student_score_manager.js', tags.IifeHandler)
       ]

    namespaced_routes = [
         (TeacherHandler.URL, TeacherHandler),
         (teacher_rest_handlers.CourseSectionRestHandler.URL, teacher_rest_handlers.CourseSectionRestHandler),
         (teacher_rest_handlers.StudentProgressRestHandler.URL, teacher_rest_handlers.StudentProgressRestHandler),
         (teacher_rest_handlers.ActivityScoreRestHandler.URL, teacher_rest_handlers.ActivityScoreRestHandler)
        ]

    dashboard_handlers = [
        ('/post_teacher_reg', TeacherHandler),
    ]

    global custom_module  # pylint: disable=global-statement
    custom_module = custom_modules.Module(
        'Teacher Dashboard Module',
        'A module to provide teacher workflow.',
        global_routes, namespaced_routes,
        notify_module_enabled=notify_module_enabled)

    return custom_module
