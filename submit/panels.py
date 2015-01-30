from pyramid_layout.panel import panel_config


@panel_config(name='navbar', renderer='templates/panels/navbar.pt')
def navbar(context, request):
    def nav_item(name, url, item_id=None):
        active = request.current_route_path() == url
        return {'active': active, 'name': name, 'url': url, 'id': item_id}

    title = 'submit.cs'
    nav = []
    path = request.route_path
    if request.user:
        nav.append(nav_item('Home', path('user_item',
                                         username=request.user.username)))
        if request.user.is_admin:
            nav.append(nav_item('Create Class', path('class_new')))
        else:
            nav.append(nav_item('Join Class', path('user_join')))
        nav.append(nav_item('Logout', '#', 'logout_btn'))
        title += ' ({})'.format(request.user.name)
    else:
        nav.append(nav_item('Login', path('session')))
        nav.append(nav_item('Create Account', path('user_new')))
    return {'nav': nav, 'title': title}


@panel_config(name='messages', renderer='templates/panels/messages.pt')
def messages(context, request):
    return {x: request.session.pop_flash(x) for x in
            ('errors', 'infos', 'successes', 'warnings')}
