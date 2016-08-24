# Copyright 2016 Mobile CSP Project All rights Reserved.
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

__author__ = 'barok.imana@trincoll.edu'
__author__ = 'ram8647@trincoll.edu'

import datetime
import logging

from google.appengine.ext import db

from common import schema_fields
from common import utils as common_utils

from controllers import utils

from models import entities
from models import models
from models import resources_display
from models import roles
from models import transforms
from models.models import MemcacheManager

# In our module
import messages
from teacher_entity import TeacherRights

class CourseSectionEntity(entities.BaseEntity):

    """Course section information"""
    name = db.StringProperty(indexed=False)
    acadyr = db.StringProperty(indexed=False)
    description = db.StringProperty(indexed=False)
    is_active = db.BooleanProperty(indexed=False)
    date = db.DateProperty()
    students = db.TextProperty(indexed=False)
    section_id = db.StringProperty(indexed=True)    
    labels = db.StringProperty(indexed=False)

    memcache_key = 'sections'

    @classmethod
    def get_sections(cls, allow_cached=True):
        sections = MemcacheManager.get(cls.memcache_key)
        if not allow_cached or sections is None:
            sections = CourseSectionEntity.all().order('-date').fetch(1000)
            MemcacheManager.set(cls.memcache_key, sections)
        return sections

    @classmethod
    def make(cls, name, acadyr, description, is_active):
        entity = cls()
        entity.name = name
        entity.acadyr = acadyr
        entity.description = description
        entity.is_active = is_active
        entity.date = datetime.datetime.now().date()
        entity.students = ""
        return entity

    def put(self):
        """Do the normal put() and also invalidate memcache."""
        result = super(CourseSectionEntity, self).put()
        MemcacheManager.delete(self.memcache_key)
        return result

    def delete(self):
        """Do the normal delete() and invalidate memcache."""
        super(CourseSectionEntity, self).delete()
        MemcacheManager.delete(self.memcache_key)

class SectionItemRESTHandler(utils.BaseRESTHandler):
    """Provides REST API for adding a section."""

    URL = '/rest/section/item'

    @classmethod
    def SCHEMA(cls):
        schema = schema_fields.FieldRegistry('CourseSection',
            extra_schema_dict_values={
                'className': 'inputEx-Group new-form-layout'})
        schema.add_property(schema_fields.SchemaField(
            'key', 'ID', 'string', editable=False, hidden=True))
        schema.add_property(schema_fields.SchemaField(
            'name', 'Name', 'string',
            description=messages.SECTION_NAME_DESCRIPTION))
        schema.add_property(schema_fields.SchemaField(
            'description', 'Description', 'string',
            description=messages.SECTION_BLURB_DESCRIPTION))
        schema.add_property(schema_fields.SchemaField(
            'acadyr', 'Academic Year', 'string',
            description=messages.ACADEMIC_YEAR_DESCRIPTION))
        resources_display.LabelGroupsHelper.add_labels_schema_fields(
            schema, 'section')
        return schema

    def get(self):
        """Handles REST GET verb and returns an object as JSON payload."""
        key = self.request.get('key')

        try:
            entity = CourseSectionEntity.get(key)
        except db.BadKeyError:
            entity = None

        if not entity:
            transforms.send_json_response(
                self, 404, 'Course Section not found.', {'key': key})
            return

        viewable = TeacherRights.apply_rights(self, [entity])
        if not viewable:
            transforms.send_json_response(
                self, 401, 'Access denied.', {'key': key})
            return
        entity = viewable[0]

        schema = SectionItemRESTHandler.SCHEMA()

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
        logging.debug('***RAM*** put (saving) ' + str(request))
        key = request.get('key')

#         if not self.assert_xsrf_token_or_fail(
#                 request, 'section-put', {'key': key}):
#             return

        if not TeacherRights.can_edit(self):
            transforms.send_json_response(
                self, 401, 'Access denied.', {'key': key})
            return

        entity = CourseSectionEntity.get(key)
        if not entity:
            transforms.send_json_response(
                self, 404, 'Course Section not found.', {'key': key})
            return

        schema = SectionItemRESTHandler.SCHEMA()

        payload = request.get('payload')
        update_dict = transforms.json_to_dict(
            transforms.loads(payload), schema.get_json_schema_dict())

#        # The datetime widget returns a datetime object and we need a UTC date.
#        update_dict['date'] = update_dict['date'].date()

        entity.labels = common_utils.list_to_text(
            resources_display.LabelGroupsHelper.field_data_to_labels(
                update_dict))
        resources_display.LabelGroupsHelper.remove_label_field_data(update_dict)

        transforms.dict_to_entity(entity, update_dict)

        logging.debug('***RAM*** entity = ' + str(entity))

        entity.put()

        transforms.send_json_response(self, 200, 'Saved.')

    def delete(self):
        """Deletes a section."""
        key = self.request.get('key')

        if not self.assert_xsrf_token_or_fail(
                self.request, 'section-delete', {'key': key}):
            return

        if not TeacherRights.can_delete(self):
            self.error(401)
            return

        entity = CourseSectionEntity.get(key)
        if not entity:
            transforms.send_json_response(
                self, 404, 'Course Section not found.', {'key': key})
            return

        entity.delete()

        transforms.send_json_response(self, 200, 'Deleted.')
