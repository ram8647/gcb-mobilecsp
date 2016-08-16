from controllers import utils
class ResourcesHandler(utils.BaseHandler):
       """Handler for Resources page."""
       def get(self):
          """Handles GET requests."""
          self.template_value['navbar'] = {'resources': True}
          self.render('resources.html')

