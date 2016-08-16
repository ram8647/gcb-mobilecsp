/**
 * This file contains the classes to manage Section Mapping widgets.
 *  Modified version of the skill_tagging_lib.js
 */

var SECTION_API_VERSION = '1';
var ESC_KEY = 27;
var MAX_SECTION_REQUEST_SIZE = 10;

/*********************** Start Dependencies ***********************************/
// The following symols are required to be defined in the global scope:
//   cbShowMsg, cbShowMsgAutoHide
var showMsg = cbShowMsg;
var showMsgAutoHide = cbShowMsgAutoHide;
/************************ End Dependencies ************************************/

function parseAjaxResponse(s) {
  // XSSI prefix. Must be kept in sync with models/transforms.py.
  var xssiPrefix = ")]}'";
  return JSON.parse(s.replace(xssiPrefix, ''));
}

/**
 * InputEx adds a JSON prettifier to Array and Object. This works fine for
 * InputEx code but breaks some library code (e.g., jQuery.ajax). Use this
 * to wrap a function which should be called with the InputEx extras turned
 * off.
 *
 * @param f {function} A zero-args function executed with prettifier removed.
 */
function withInputExFunctionsRemoved(f) {
  var oldArrayToPrettyJsonString = Array.prototype.toPrettyJSONString;
  var oldObjectToPrettyJsonString = Object.prototype.toPrettyJSONString;
  delete Array.prototype.toPrettyJSONString;
  delete Object.prototype.toPrettyJSONString;

  try {
    f();
  } finally {
    if (oldArrayToPrettyJsonString !== undefined) {
      Array.prototype.toPrettyJSONString = oldArrayToPrettyJsonString;
    }
    if (oldObjectToPrettyJsonString !== undefined) {
      Object.prototype.toPrettyJSONString = oldObjectToPrettyJsonString;
    }
  }
}

/**
 * A sections table builder.
 *
 * @class
 */
function SectionTable(sectionList) {
  this._sectionList = sectionList;
}

SectionTable.prototype = {
  _buildRow: function(section) {
    var tr = $('<tr class="row"></tr>');

    // add button to view/edit roster
    var td = $(
        '<td class="roster">' +
        '  <a class="gcb-button" role="button" href="/' + window.course_namespace +
        '/modules/teacher_dashboard?action=teacher_dashboard' +
        '&tab=sections&tab_action=roster&section=' + section.id + '">' +
        '    View Roster' +
        '  </a>' +
        '</td>'
    );
    tr.append(td);

    // add section name
    var td = $(
        '<td class="section">' +
        '  <div class="diagnosis icon md"></div>' +
        '  <span class="section-name"></span> ' +
        '  <button class="icon md md-mode-edit reveal-on-hover edit-section"></button> ' +
        '</td>'
    );

    td.find('.diagnosis.icon, button').data('id', section.id);

    td.find('.section-name').text(section.name);
    tr.append(td);

    // add section year
    var td = $(
        '<td class="year">' +
        '  <span class="section-year"></span>' +
        '</td>'
    );

    td.find('.section-year').text(section.year);
    tr.append(td);

    // add section description
    var td = $(
        '<td class="description">' +
          '<span class="section-description"></span>' +
        '</td>'
    );
    td.find('.section-description').text(section.description);
    tr.append(td);

    // add section status ((in)active)
    var td = $(
        '<td class="active">' +
          '<input type="checkbox" disabled class="section-active" />' +
        '</td>'
    );
    if (section.active || section.active.toString().toLowerCase() === 'true') {
        td.find('.section-active').prop('checked', true);
    }
    tr.append(td);

    return tr;
  },

  _sectionsCount: function() {
    var that = this;
    return Object.keys(that._sectionList._sectionLookupByIdTable).length;
  },

  _buildHeader: function() {
    var that = this;
    var thead = $(
      '<thead>' +
      '  <tr>' +
      '    <th></th>' +
      '    <th class="section">Section <span class="section-count"></span></th>' +
      '    <th class="year">Year</th>' +
      '    <th class="description">Description</th>' +
      '    <th class="active">Status</th>' +
      '  </tr>' +
      '</thead>'
    );
    thead.find('.section-count').text('(' + that._sectionsCount() + ')')
    return thead;
  },

  _buildBody: function() {
    var that = this;
    var tbody = $('<tbody></tbody>');

    var i = 0;
    that._sectionList.eachSection(function(section) {
      var row = that._buildRow(section);
      row.addClass( i++ % 2 == 0 ? 'even' : 'odd');
      tbody.append(row);
    });

    tbody.find('.edit-section').on('click', function(e){
      var sectionId = $(this).data('id');
      var sectionPopUp = new EditSectionPopup(that._sectionList,
          sectionId);
      sectionPopUp.open(function() {
        that._refresh();
      });
    });

    return tbody;
  },

  _refresh: function() {
    this._table.find('tbody').remove();
    this._table.append(this._buildBody());
  },

  buildTable: function() {
    var that = this;

    this._content = $(
      '<div class="controls" style="margin: 10px;">' +
      '  <button class="gcb-button add-new-section">+ Create New Section</button>' +
      '  <br />' +
      '  <input style="margin-top: 15px;" type="checkbox" class="view-active" checked /><label>Show Inactive' +
      '    Courses</label>' +
      '</div>' +
      '<h3>Sections</h3>' +
      '<table class="sections-table"></table>');

    this._table = this._content.filter('table.sections-table');
    this._table.append(that._buildHeader());

    this._content.find('.add-new-section').on("click", function() {
      var sectionPopUp = new EditSectionPopup(that._sectionList);
      sectionPopUp.open(function() {
        that._refresh();
      });
    });

    this._content.find('.view-active').on("click", function() {
        var showInactive = $(this).prop('checked');

        if (!showInactive) {
            $('.sections-table > tbody > tr').each(function (index, value) {

                var active = $(this).find('.section-active').prop('checked');
                if (active) {
                    $(this).css('display', 'table-row');
                }
                else {
                    $(this).css('display', 'none');
                }
            });
        }
        else
        {
            $('.sections-table > tbody > tr').each(function (index, value) {
                $(this).css('display', 'table-row');
            });
        }
    });

    this._refresh();

    return this._content;
  }
};

/**
 * A proxy to load and work with a list of skills from the server. Each of the
 * skills is an object with fields for "id", "name", and "description".
 *
 * @class
 */
function SectionList() {
  this._sectionLookupByIdTable = {};
  this._xsrfToken = null;
}

SectionList.prototype = {
  /**
   * Load the section list from the server.
   *
   * @method
   * @param callback {function} A zero-args callback which is called when the
   *     section list has been loaded.
   */
  load: function(callback) {
    var that = this;
    $.ajax({
      type: 'GET',
      url: 'rest/modules/teacher_dashboard/section',
      dataType: 'text',
      success: function(data) {
        that._onLoad(callback, data);
      },
      error: function(error) {
        showMsg('Can\'t load the sections list.');
      }
    });
  },

  /**
   * @param id {string}
   * @return {object} The section with given id, or null if no match.
   */
  getSectionById: function(id) {
    return this._sectionLookupByIdTable[id];
  },

  /**
   * Iterate over the section in the list.
   *
   * @param callback {function} A function taking a section as its arg.
   */
  eachSection: function(callback) {
    for (var prop in this._sectionLookupByIdTable) {
      if (this._sectionLookupByIdTable.hasOwnProperty(prop)) {
        callback(this._sectionLookupByIdTable[prop]);
      }
    }
  },

  /**
   * Create a new section and store it on the server.
   *
   * @param callback {function} A callback which takes (section, message) args
   * @param name {string}
   * @param description {string}
   * @param sectionId
   */
  createOrUpdateSection: function(callback, name, description, active, year, sectionId) {

    var that = this;

    if (! name) {
      showMsg('Name can\'t be empty');
      return;
    }

    var requestDict = {
      xsrf_token: this._xsrfToken,
      payload: JSON.stringify({
        'version': SECTION_API_VERSION,
        'name': name,
        'description': description,
        'active': active,
        'students': null,
        'year': year
      })
    };
    if (sectionId) {
      requestDict['key'] = sectionId;
    }

    var request = JSON.stringify(requestDict);

    withInputExFunctionsRemoved(function() {
      $.ajax({
        type: 'PUT',
        url: 'rest/modules/teacher_dashboard/section',
        data: {'request': request},
        dataType: 'text',
        success: function(data) {
          that._onCreateOrUpdateSection(callback, data);
        }
      });
    });
  },

  _onLoad: function(callback, data) {
    data = parseAjaxResponse(data);
    if (data.status != 200) {
      showMsg('Unable to load section list. Reload page and try again.');
      return;
    }
    this._xsrfToken = data['xsrf_token'];
    var payload = JSON.parse(data['payload']);
    this._updateFromPayload(payload);

    if (callback) {
      callback();
    }
  },

  _updateFromPayload: function(payload) {
    var that = this;
    var sectionList = payload['section_list'];

    this._sectionLookupByIdTable = [];
    $.each(sectionList, function() {
      that._sectionLookupByIdTable[this.id] = this;
    });
  },

  _onCreateOrUpdateSection: function(callback, data) {
    data = parseAjaxResponse(data);
    if  (data.status != 200) {
      showMsg(data.message);
      return;
    }
    var payload = JSON.parse(data.payload);
    this._updateFromPayload(payload);

    if (callback) {
      callback(payload.section, data.message);
    }
  }
};



/**
 * A class to put up a modal lightbox. Use setContent to set the DOM element
 * displayed in the lightbox.
 *
 * @class
 */
function Lightbox() {
  this._window = $(window);
  this._container = $('<div class="lightbox"/>');
  this._background = $('<div class="background"/>');
  this._content = $('<div class="content"/>');

  this._container.append(this._background);
  this._container.append(this._content);
  this._container.hide();
}
Lightbox.prototype = {
  /**
   * Set a DOM element to root the lightbox in. Typically will be document.body.
   *
   * @param rootEl {Node}
   */
  bindTo: function(rootEl) {
    $(rootEl).append(this._container);
    return this;
  },
  /**
   * Show the lightbox to the user.
   */
  show: function() {
    this._container.show();
    var top = this._window.scrollTop() +
        Math.max(8, (this._window.height() - this._content.height()) / 2);
    var left = this._window.scrollLeft() +
        Math.max(8, (this._window.width() - this._content.width()) / 2);

    this._content.css('top', top).css('left', left);
    return this;
  },
  /**
   * Close the lightbox and remove it from the DOM.
   */
  close: function() {
    this._container.remove();
    return this;
  },
  /**
   * Set the content shown in the lightbox.
   *
   * @param contentEl {Node or jQuery}
   */
  setContent: function(contentEl) {
    this._content.empty().append(contentEl);
    return this;
  }
};

/**
 * A modal popup to edit or add sections.
 *
 * @class
 * @param sectionList {SectionList}
 * @param sectionId {string} If the sectionId is null, the editor will be configured
 *     to create a new section rather that edit an existing one.
 */
function EditSectionPopup(sectionList, sectionId) {
  var that = this;
  this._sectionId = sectionId;
  this._sectionList = sectionList;
  this._documentBody = $(document.body);
  this._lightbox = new Lightbox();
  this._form = $(
      '<div class="edit-section-popup">' +
      '  <h2 class="title" style="text-align: center; margin-left: 0px;"></h2>' +
      '  <div class="course-name" style="margin: 15px;">' +
      '    <label name="course_name_lbl">Enter Course Name:</label>' +
      '    <input style="margin-left: 3px;" type="text" name="section_name" class="section-name gcb-pull-right" />' +
      '  </div>' +
      '  <div class="course-date" style="margin: 15px;">' +
      '    <label name="course_date_lbl">Academic Year:</label>' +
      '    <select class="section-year gcb-pull-right">' +
      '      <option value="2015-2016">2015-2016</option>' +
      '      <option value="2016-2017">2016-2017</option>' +
      '      <option value="2017-2018">2017-2018</option>' +
      '      <option value="2018-2019">2018-2019</option>' +
      '    </select>' +
      '  </div>' +
      '  <div class="course-active" style="margin: 15px;">' +
      '    <label name="active_lbl">Course Active</label>' +
      '    <input type="checkbox" class="section-active gcb-pull-right" value="True" text="Course Active" checked />' +
      '  </div>' +
      '  <div class="course-description" style="margin: 15px;">' +
      '    <label name="course_description_lbl" style="vertical-align: top;">Course Description:</label>' +
      '    <textarea class="section-description" cols="25" rows="5"></textarea>' +
      '  </div>' +
      '  <div class="controls" style="margin-left: auto; margin-right: auto; text-align: center;">' +
      '    <button class="gcb-button new-section-save-button">Save</button>' +
      '    <button class="gcb-button new-section-cancel-button">Cancel</button>' +
      '</div>');

  this._nameInput = this._form.find('.section-name');
  this._descriptionInput = this._form.find('.section-description');
  this._activeInput = this._form.find('.section-active');
  this._yearInput = this._form.find('.section-year');

  if (sectionId !== null && sectionId !== undefined) {
    var section = this._sectionList.getSectionById(sectionId);
    var title = 'Edit Section';
    $(this._nameInput).attr('disabled', true);
    this._nameInput.val(section.name);
    this._descriptionInput.val(section.description);
    this._activeInput.prop("checked", section.active)
    this._yearInput.val(section.year);
  } else {
    var title = 'Create New Section';
  }

  this._form.find('h2.title').text(title);

  this._form.find('button.new-section-save-button').click(function() {
    cbShowMsg('Saving...');
    that._onSave();
    return false;
  });

  this._form.find('button.new-section-cancel-button')
    .click(function() {
      that._onCancel();
      return false;
    }
  );
}

EditSectionPopup.prototype = {
  /**
   * Display the popup to the user.
   *
   * @param callback {function} Called with the new section after a section is
   *     added. The section is automatically added to the SectionList, so there is
   *     no need to update the SectionList in the callback.
   */
  open: function(callback) {
    this._onAjaxCreateSectionCallback = callback;
    this._lightbox
      .bindTo(this._documentBody)
      .setContent(this._form)
      .show();
    $('.section-name').focus();

    var that = this;
    $(document).on('keydown', function(e) {
      if (e.which == ESC_KEY) {
        that._lightbox.close();
        $(document).unbind('keydown');
      }
    });

    return this;
  },

  _onSave: function() {
    var that = this;
    var name = this._nameInput.val();
    var description = this._descriptionInput.val();
    var active = this._activeInput.prop('checked');
    var year = this._yearInput.val();

    function onSectionCreatedOrUpdated(section, message) {
      showMsgAutoHide(message);
      that._onAjaxCreateSectionCallback(section);
    }
    this._sectionList.createOrUpdateSection(onSectionCreatedOrUpdated, name,
        description, active, year, that._sectionId);
    this._lightbox.close();
  },

  _onCancel: function() {
    this._lightbox.close();
  }
};


/**
 * A container to display a list of items as labels with buttons for removal.
 *
 * @class
 * @param listClass {string} The CSS class for the container.
 * @param itemClass {string} The CSS class for each item in the list.
 * @param onRemoveCallback {function} Called with the id of an item whenever an
 *     item is removed from the view.
 */
function ListDisplay(listClass, itemClass, onRemoveCallback) {
  this._ol = $('<ol></ol>');
  this._ol.addClass(listClass);
  this._itemClass = itemClass;
  this._onRemoveCallback = onRemoveCallback;
  this._items = {};
}

ListDisplay.prototype = {
  /**
   * Remove all item from the view.
   *
   * @method
   */
  empty: function() {
    this._ol.empty();
    this._items = {};
  },

  /**
   * Add a new item to the view.
   *
   * @method
   * @param id {string} The item id, which is passed to the onRemoveCallback.
   * @param label {string} The labl of the item to be displayed in the list.
   */
  add: function(id, label) {
    var that = this;
    var li = $('<li></li>');
    var closeButton = $('<button class="close">x</button>');

    // Refuse to add an existing element
    if (this._items[id]) {
      return;
    }

    li.addClass(this._itemClass).text(label).append(closeButton);

    closeButton.click(function() {
      li.remove();
      delete that._items[id];
      if (that._onRemoveCallback) {
        that._onRemoveCallback(id);
      }
      return false;
    });

    this._ol.append(li);
    this._items[id] = true;
  },

  /**
   * @return {Element} The root DOM element for the display.
   */
  element: function() {
    return this._ol[0];
  },

  /**
   * @return {Array} The list of item id's which are in the display.
   */
  items: function() {
    var that = this;
    return $.map(this._items, function(flag, id) {
      return that._items.hasOwnProperty(id) ? id : null;
    });
  }
};

/**
 * A class to display a widget for item selection.
 *
 * @class
 * @param onItemsSelectedCallback {function} Callback called with a list of
 *     item ids whenever a selection is performed.
 * @param addLabel {string} Optional label for ADD button.
 */
function ItemSelector(onItemsSelectedCallback, label, placeholder) {
  this._documentBody = $(document.body);
  this._onItemsSelectedCallback = onItemsSelectedCallback;

  label = label || '+ Add';
  placeholder = placeholder || 'Section...';

  this._rootDiv = $(
    '<div class="item-selector-root">' +
    '  <button class="add"></button>' +
    '  <div class="selector">' +
    '    <div><input class="search" type="text"></div>' +
    '    <ol class="item-list"></ol>' +
    '    <div><button class="select action">OK</button></div>' +
    '  </div>' +
    '</div>');
  this._rootDiv.find('button.add').text(label);
  this._rootDiv.find('input.search').attr('placeholder', placeholder);

  this._addItemButton = this._rootDiv.find('button.add');
  this._addItemWidgetDiv = this._rootDiv.find('div.selector');
  this._searchTextInput = this._rootDiv.find('input.search');
  this._selectNewItemButton = this._rootDiv.find('button.select');
  this._selectItemListOl = this._rootDiv.find('ol.item-list');

  this._addItemButton.prop('disabled', true);
  this._selectNewItemButton.prop('disabled', true);

  this._bind();
  this._close();
}

ItemSelector.prototype = {
  /**
   * @method
   * @return {Element} The root DOM element for the selector.
   */
  element: function() {
    return this._rootDiv[0];
  },
  /**
   * Add an item to the selector.
   *
   * @method
   * @param id {string} the id of the item
   * @param name {string} the display name of the item
   */
  add: function(id, name) {
    var that = this;
    var itemLi = $('<li/>');
    var label = $('<label></label>');
    var checkbox = $('<input type="checkbox" class="item-select">');

    checkbox.change(function() {
      if (that._addItemWidgetDiv.find('input.item-select:checked').length) {
        that._selectNewItemButton.prop('disabled', false);
      } else {
        that._selectNewItemButton.prop('disabled', true);
      }
    });

    checkbox.data('id', id);

    label.append(checkbox);
    label.append($('<span></span>').text(name));

    itemLi.append(label);
    this._selectItemListOl.append(itemLi);

    this._addItemButton.prop('disabled', false);
  },
  clear: function() {
    this._selectItemListOl.empty();
    this._addItemButton.prop('disabled', true);
  },
  _bind: function() {
    var that = this;

    this._addItemButton.click(function() {
      that._addItemWidgetDiv.show();
      that._positionAddItemWidgetDiv();
      return false;
    });

    this._documentBody.click(function(evt) {
      if ($(evt.target).closest('div.selector').length == 0) {
        that._close();
      }
    });

    this._searchTextInput.keyup(function(evt) {
      that._filterAddItemWidget(that._searchTextInput.val());
    });

    this._selectNewItemButton.click(function() {
      that._selectItems();
      that._close();
      return false;
    });
  },
  /**
   * Choose an optimal position for the addItemWidgetDiv.
   */
  _positionAddItemWidgetDiv: function() {
    // PADDING = (margin used in CSS styling) - (extra padding)
    PADDING = 22 - 10;

    // Remove any previous styling
    this._addItemWidgetDiv.css('top', null);

    var bounds = this._addItemWidgetDiv[0].getBoundingClientRect();
    var overflow = bounds.bottom - $(window).height();
    var top = PADDING - overflow;
    if (overflow > 0 && top + bounds.top >= 0) {
      this._addItemWidgetDiv.css('top', top);
    }
  },
  _close: function() {
    this._addItemWidgetDiv.hide();
    this._searchTextInput.val('');
    this._selectItemListOl.find('li').show();
    this._addItemWidgetDiv.find('input.item-select').prop('checked', false);
    this._selectNewItemButton.prop('disabled', true);
  },

  _filterAddItemWidget: function(filter) {
    filter = filter.toLowerCase();
    this._selectItemListOl.find('> li').show();
    this._selectItemListOl.find('> li span').each(function() {
      if ($(this).text().toLowerCase().indexOf(filter) == -1) {
        $(this).closest('li').hide();
      }
    });
  },

  _selectItems: function() {
    var that = this;
    var selectedItems = this._addItemWidgetDiv
        .find('input.item-select:checked')
        .map(function() {
          return $(this).data('id');
        });
    this._onItemsSelectedCallback(selectedItems);
  }
}

function SectionEditorForOeditor(env) {
  var that = this;

  this._env = env;
  this._sectionList = new SectionList();

  var newSectionDiv = $('<div class="new-section"></div>');
  var newSectionButton = $('<button class="add">+ Create New section</button>');
  newSectionButton.click(function() {
    new EditSectionPopup(that._sectionList, null, null).open(function(section) {
      that._onSectionsSelectedCallback([section.id]);
      that._populatePrereqSelector();
    });
    return false;
  });
  newSectionDiv.append(newSectionButton);

  this._sectionWidgetDiv = $('<div class="inputEx-Field"></div>');
  this._sectionWidgetDiv.append(this._prereqDisplay.element());

  var buttonDiv = $('<div class="section-buttons"></div>');
  this._sectionWidgetDiv.append(buttonDiv);
  buttonDiv.append(newSectionDiv);
}

SectionEditorForOeditor.prototype = {
  element: function() {
    return this._sectionWidgetDiv;
  },
  init: function() {
    var that = this;
    this._sectionList.load(function() {
      that._populateSectionList();
    });
  },
  _onSectionsSelectedCallback: function(selectedSectionIds) {
    // When new sections are selected in the SectionSelector, update the OEditor
    // form and repopulate the SectionDisplay.
    var that = this;
    $.each(selectedSectionIds, function() {
      if (! that._formContainsSectionId(this)) {
        that._env.form.inputsNames.sections.addElement({'section': this});
      }
    });
    this._populateSectionList();
  },
  _onRemoveCallback: function (sectionId) {
    // When a section is removed from the SectionDisplay, also remove it from the
    // OEditor form.
    var that = this;
    $.each(this._env.form.inputsNames.sections.subFields, function(i) {
      var id = this.inputsNames.section.getValue();
      if (id === sectionId) {
        that._env.form.inputsNames.sections.removeElement(i);
        return false;
      }
    });
  },
  _populateSectionList: function() {
    // Populate the SectionDisplay with the sections in the OEditor form.
    var that = this;
    $.each(this._env.form.inputsNames.sections.subFields, function() {
      var id = this.inputsNames.section.getValue();
      var section = that._sectionList.getSectionById(id);
    });
  },
  _formContainsSectionId: function(sectionId) {
    var fields = this._env.form.inputsNames.sections.subFields;
    for(var i = 0; i < fields.length; i++) {
      var id = fields[i].inputsNames.section.getValue();
      if (sectionId.toString() === id.toString()) {
        return true;
      }
    }
    return false;
  }
};

/**
 * Export the classes which will be used in global scope.
 */
window.SectionEditorForOeditor = SectionEditorForOeditor;
window.SectionList = SectionList;
window.SectionTable = SectionTable;