from pyramid_layout.layout import layout_config


@layout_config(template='templates/layouts/main.pt')
class MainLayout(object):
    page_title = 'UCSB Computer Science Submission Service'

    def __init__(self, context, request):
        self.context = context
        self.request = request
