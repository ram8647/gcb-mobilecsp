from controllers import utils
class PrivacyHandler(utils.BaseHandler):
       """Handler for Privacy page."""
       def get(self):
          """Handles GET requests."""
          self.template_value['navbar'] = {'privacy': True}
          self.render('privacy.html')

