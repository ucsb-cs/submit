from pyramid_layout.panel import panel_config


@panel_config(name='navbar', renderer='nudibranch:templates/panels/navbar.pt')
def navbar(context, request):
    def nav_item(name, url):
        active = request.current_route_path() == url
        return {'active': active, 'name': name, 'url': url}

    title = 'submit.cs'
    nav = []
    if request.user:
        nav.append(nav_item('Home', request.route_path(
                    'user_item', username=user.username)))
        nav.append(nav_item('Logout', request.route_path('logout')))
        title += ' ({})'.format(request.user.username)
    else:
        nav.append(nav_item('Login', request.route_path('session')))
    return {'nav': nav, 'title': title}


@panel_config(name='messages',
              renderer='nudibranch:templates/panels/messages.pt')
def messages(context, request):
    return {x: request.session.pop_flash(x) for x in
            ('errors', 'infos', 'successes', 'warnings')}
