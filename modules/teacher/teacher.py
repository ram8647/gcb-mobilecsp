# Copyright 2012 Google Inc. All Rights Reserved.
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

"""Classes and methods to create and manage Teachers."""

__author__ = 'Saifu Angto (saifu@google.com)'


import cgi
import datetime
import os
import urllib

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

MODULE_NAME = 'teacher'
MODULE_TITLE = 'Teacher'

#Setup paths and directories for templates and resources
RESOURCES_PATH = '/modules/teacher/resources'
TEMPLATES_DIR = os.path.join(
    appengine_config.BUNDLE_ROOT, 'modules', MODULE_NAME, 'templates')

class TeacherRights(object):
    """Manages view/edit rights for teachers."""

    @classmethod
    def can_view(cls, unused_handler):
        return True

    @classmethod
    def can_edit(cls, handler):
        return roles.Roles.is_course_admin(handler.app_context)

    @classmethod
    def can_delete(cls, handler):
        return cls.can_edit(handler)

    @classmethod
    def can_add(cls, handler):
        return cls.can_edit(handler)

    @classmethod
    def apply_rights(cls, handler, items):
        """Filter out items that current user can't see."""
        if TeacherRights.can_edit(handler):
            return items

        allowed = []
        for item in items:
            allowed.append(item)

        return allowed


class TeacherHandlerMixin(object):
    def get_teacher_action_url(self, action, key=None):
        args = {'action': action}
        if key:
            args['key'] = key
        return self.canonicalize_url(
            '{}?{}'.format(
                MyTeacherDashboardHandler.URL, urllib.urlencode(args)))

    def format_items_for_template(self, items):
        """Formats a list of entities into template values."""
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
                item['edit_action'] = self.get_teacher_action_url(
                    MyTeacherDashboardHandler.EDIT_ACTION, key=item['key'])

                item['delete_xsrf_token'] = self.create_xsrf_token(
                    MyTeacherDashboardHandler.DELETE_ACTION)
                item['delete_action'] = self.get_teacher_action_url(
                    MyTeacherDashboardHandler.DELETE_ACTION,
                    key=item['key'])

            template_items.append(item)

        output = {}
        output['children'] = template_items

        # add 'add' action
        if TeacherRights.can_edit(self):
            output['add_xsrf_token'] = self.create_xsrf_token(
                MyTeacherDashboardHandler.ADD_ACTION)
            output['add_action'] = self.get_teacher_action_url(
                MyTeacherDashboardHandler.ADD_ACTION)

        return output


class TeacherStudentHandler(
        TeacherHandlerMixin, utils.BaseHandler,
        utils.ReflectiveRequestHandler):
    URL = '/teacher'
    default_action = 'sections'
#    default_action = 'list'
    get_actions = [default_action]
    post_actions = []

    def get_sections(self):
        """Renders Sections view. Javascript handles getting course sections and building the view"""
        template_values = {}
        template_values['namespace'] = self.get_course()._namespace.replace('ns_', '')
        template_values['ralph'] = 'ralphie'

        main_content = self.get_template(
            'teacher_sections.html', [TEMPLATES_DIR]).render(template_values)

        self.response.write(main_content)

    def _render_page(self, template):
        self.template_value['navbar'] = {'teacher': True}
        self.render(template)


    def get_list(self):
        """Shows a list of teachers."""
        student = None
        user = self.personalize_page_and_get_user()
        transient_student = False
        if user is None:
            transient_student = True
        else:
            student = Student.get_enrolled_student_by_user(user)
            if not student:
                transient_student = True
        self.template_value['transient_student'] = transient_student
        items = TeacherEntity.get_teachers()
        items = TeacherRights.apply_rights(self, items)
        if not roles.Roles.is_course_admin(self.get_course().app_context):
            items = models.LabelDAO.apply_course_track_labels_to_student_labels(
                self.get_course(), student, items)

        self.template_value['teachers'] = self.format_items_for_template(
            items)
        self._render()

    def _render(self):
        self.template_value['navbar'] = {'teacher': True}
        self.render('teachers.html')


class MyTeacherDashboardHandler(
        TeacherHandlerMixin, dashboard.DashboardHandler):
    """Handler for teachers."""

    LIST_ACTION = 'edit_teachers'
    EDIT_ACTION = 'edit_teacher'
    DELETE_ACTION = 'delete_teacher'
    ADD_ACTION = 'add_teacher'

    get_actions = [LIST_ACTION, EDIT_ACTION]
    post_actions = [ADD_ACTION, DELETE_ACTION]

    LINK_URL = 'edit_teachers'
    URL = '/{}'.format(LINK_URL)
    LIST_URL = '{}?action={}'.format(LINK_URL, LIST_ACTION)

    @classmethod
    def get_child_routes(cls):
        """Add child handlers for REST."""
        return [
            (TeacherItemRESTHandler.URL, TeacherItemRESTHandler)]

    def get_edit_teachers(self):
        """Shows a list of teachers."""
        items = TeacherEntity.get_teachers()
        items = TeacherRights.apply_rights(self, items)

        main_content = self.get_template(
            'teacher_list.html', [TEMPLATES_DIR]).render({
                'teachers': self.format_items_for_template(items),
            })

        self.render_page({
            'page_title': self.format_title('Teachers'),
            'main_content': jinja2.utils.Markup(main_content)})

    def get_edit_teacher(self):
        """Shows an editor for an teacher."""

        key = self.request.get('key')

        schema = TeacherItemRESTHandler.SCHEMA()

        exit_url = self.canonicalize_url('/{}'.format(self.LIST_URL))
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

        self.render_page({
            'main_content': form_html,
            'page_title': 'Edit Teacher',
        }, in_action=self.LIST_ACTION)

    def _get_delete_url(self, base_url, key, xsrf_token_name):
        return '%s?%s' % (
            self.canonicalize_url(base_url),
            urllib.urlencode({
                'key': key,
                'xsrf_token': cgi.escape(
                    self.create_xsrf_token(xsrf_token_name)),
            }))

    def post_delete_teacher(self):
        """Deletes an teacher."""
        if not TeacherRights.can_delete(self):
            self.error(401)
            return

        key = self.request.get('key')
        entity = TeacherEntity.get(key)
        if entity:
            entity.delete()
        self.redirect('/{}'.format(self.LIST_URL))

    def post_add_teacher(self):
        """Adds a new teacher and redirects to an editor for it."""
        if not TeacherRights.can_add(self):
            self.error(401)
            return

        entity = TeacherEntity.make('New Teacher', '', True)
        entity.put()

        self.redirect(self.get_teacher_action_url(
            self.EDIT_ACTION, key=entity.key()))


class TeacherItemRESTHandler(utils.BaseRESTHandler):
    """Provides REST API for an teacher."""

    URL = '/rest/teacher/item'

    @classmethod
    def SCHEMA(cls):
        schema = schema_fields.FieldRegistry('Teacher',
            extra_schema_dict_values={
                'className': 'inputEx-Group new-form-layout'})
        schema.add_property(schema_fields.SchemaField(
            'key', 'ID', 'string', editable=False, hidden=True))
        schema.add_property(schema_fields.SchemaField(
            'name', 'Name', 'string',
            description=messages.TEACHER_NAME_DESCRIPTION))
        schema.add_property(schema_fields.SchemaField(
            'email', 'Email', 'string',
            description=messages.TEACHER_EMAIL_DESCRIPTION))
        schema.add_property(schema_fields.SchemaField(
            'school', 'School', 'string',
            description=messages.TEACHER_SCHOOL_DESCRIPTION))
        schema.add_property(schema_fields.SchemaField(
            'date', 'Date', 'datetime',
            description=messages.TEACHER_DATE_DESCRIPTION,
            extra_schema_dict_values={
                '_type': 'datetime',
                'className': 'inputEx-CombineField gcb-datetime '
                'inputEx-fieldWrapper date-only inputEx-required'}))
        resources_display.LabelGroupsHelper.add_labels_schema_fields(
            schema, 'teacher')
        return schema

    def get(self):
        """Handles REST GET verb and returns an object as JSON payload."""
        key = self.request.get('key')

        try:
            entity = TeacherEntity.get(key)
        except db.BadKeyError:
            entity = None

        if not entity:
            transforms.send_json_response(
                self, 404, 'Object not found.', {'key': key})
            return

        viewable = TeacherRights.apply_rights(self, [entity])
        if not viewable:
            transforms.send_json_response(
                self, 401, 'Access denied.', {'key': key})
            return
        entity = viewable[0]

        schema = TeacherItemRESTHandler.SCHEMA()

        entity_dict = transforms.entity_to_dict(entity)

        # Format the internal date object as ISO 8601 datetime, with time
        # defaulting to 00:00:00
        date = entity_dict['date']
        date = datetime.datetime(date.year, date.month, date.day)
        entity_dict['date'] = date

        entity_dict.update(
            resources_display.LabelGroupsHelper.labels_to_field_data(
                common_utils.text_to_list(entity.labels)))

        json_payload = transforms.dict_to_json(entity_dict)
        transforms.send_json_response(
            self, 200, 'Success.',
            payload_dict=json_payload,
            xsrf_token=utils.XsrfTokenManager.create_xsrf_token(
                'teacher-put'))

    def put(self):
        """Handles REST PUT verb with JSON payload."""
        request = transforms.loads(self.request.get('request'))
        key = request.get('key')

        if not self.assert_xsrf_token_or_fail(
                request, 'teacher-put', {'key': key}):
            return

        if not TeacherRights.can_edit(self):
            transforms.send_json_response(
                self, 401, 'Access denied.', {'key': key})
            return

        entity = TeacherEntity.get(key)
        if not entity:
            transforms.send_json_response(
                self, 404, 'Object not found.', {'key': key})
            return

        schema = TeacherItemRESTHandler.SCHEMA()

        payload = request.get('payload')
        update_dict = transforms.json_to_dict(
            transforms.loads(payload), schema.get_json_schema_dict())

        # The datetime widget returns a datetime object and we need a UTC date.
        update_dict['date'] = update_dict['date'].date()

        entity.labels = common_utils.list_to_text(
            resources_display.LabelGroupsHelper.field_data_to_labels(
                update_dict))
        resources_display.LabelGroupsHelper.remove_label_field_data(update_dict)

        transforms.dict_to_entity(entity, update_dict)

        entity.put()

        transforms.send_json_response(self, 200, 'Saved.')

    def delete(self):
        """Deletes an teacher."""
        key = self.request.get('key')

        if not self.assert_xsrf_token_or_fail(
                self.request, 'teacher-delete', {'key': key}):
            return

        if not TeacherRights.can_delete(self):
            self.error(401)
            return

        entity = TeacherEntity.get(key)
        if not entity:
            transforms.send_json_response(
                self, 404, 'Object not found.', {'key': key})
            return

        entity.delete()

        transforms.send_json_response(self, 200, 'Deleted.')

class TeacherEntity(entities.BaseEntity):
    """A class that represents a persistent database entity of teacher."""
    name = db.StringProperty(indexed=False)
    date = db.DateProperty()
    email = db.TextProperty(indexed=False)
    school = db.TextProperty(indexed=False)
    labels = db.StringProperty(indexed=False)

    memcache_key = 'teachers'

    @classmethod
    def get_teachers(cls, allow_cached=True):
        items = MemcacheManager.get(cls.memcache_key)
        if not allow_cached or items is None:
            items = TeacherEntity.all().order('-date').fetch(1000)

            # TODO(psimakov): prepare to exceed 1MB max item size
            # read more here: http://stackoverflow.com
            #   /questions/5081502/memcache-1-mb-limit-in-google-app-engine
            MemcacheManager.set(cls.memcache_key, items)
        return items

    @classmethod
    def make(cls, name, email, school):
        entity = cls()
        entity.name = name
        entity.date = datetime.datetime.now().date()
        entity.email = email
        entity.school = school
        return entity

    def put(self):
        """Do the normal put() and also invalidate memcache."""
        result = super(TeacherEntity, self).put()
        MemcacheManager.delete(self.memcache_key)
        return result

    def delete(self):
        """Do the normal delete() and invalidate memcache."""
        super(TeacherEntity, self).delete()
        MemcacheManager.delete(self.memcache_key)


def notify_module_enabled():
    """Handles things after module has been enabled."""

    dashboard.DashboardHandler.EXTRA_JS_HREF_LIST.append('/modules/teacher_dashboard/resources/js/popup.js')

#    transforms.CUSTOM_JSON_ENCODERS.append(teacher_entity.CourseSectionEntity.json_encoder)


custom_module = None


def register_module():
    """Registers this module in the registry."""

    handlers = [
        (handler.URL, handler) for handler in
        [TeacherStudentHandler, MyTeacherDashboardHandler]]

#    global_routes = []
    dashboard.DashboardHandler.EXTRA_JS_HREF_LIST.append('/modules/teacher_dashboard/resources/js/popup.js')

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

    dashboard.DashboardHandler.add_sub_nav_mapping(
        'analytics', MODULE_NAME, MODULE_TITLE,
        action=MyTeacherDashboardHandler.LIST_ACTION,
        href=MyTeacherDashboardHandler.LIST_URL,
        placement=1000, sub_group_name='pinned')

    global custom_module  # pylint: disable=global-statement
    custom_module = custom_modules.Module(
        MODULE_TITLE,
        'A set of pages for managing course teachers.',
        global_routes, handlers,
        notify_module_enabled=notify_module_enabled)

    return custom_module
