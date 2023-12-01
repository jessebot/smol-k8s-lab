#!/usr/bin/env python3.11
from textual import on
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll, Container, Horizontal
from textual.binding import Binding
from textual.events import Mount
from textual.widgets import (Footer, Header, Input, Label,
                             RadioButton, RadioSet, Rule, SelectionList, Static,
                             Switch, TabbedContent, TabPane)
from textual.widgets._toggle_button import ToggleButton
from textual.widgets.selection_list import Selection
from smol_k8s_lab.constants import (DEFAULT_APPS, DEFAULT_DISTRO,
                                    DEFAULT_DISTRO_OPTIONS, DEFAULT_CONFIG)


class ConfigureAll(App):
    """
    class helps the user configure specific custom values for applications such
    as hostnames and timezones
    """
    CSS_PATH = "./css/configure_all.tcss"
    BINDINGS = [
        Binding(key="tab",
                action="focus_next",
                description="Focus next",
                show=True),
        Binding(key="q",
                key_display="q",
                action="quit",
                description="Quit smol-k8s-lab")
    ]
    ToggleButton.BUTTON_INNER = '♥'

    def compose(self) -> ComposeResult:
        """
        Compose app with tabbed content.
        """
        header = Header()
        header.tall = True
        yield header
        # Footer to show keys
        yield Footer()

        # Add the TabbedContent widget
        with TabbedContent(initial="select-distro"):
            # tab 1 - select a kubernetes distro
            with TabPane("Select k8s distro", id="select-distro"):
                with RadioSet():
                    # create all the radio button choices
                    for distro in sorted(DEFAULT_DISTRO_OPTIONS.keys()):
                        enabled = False

                        if distro == DEFAULT_DISTRO:
                            enabled = True

                        # note that k3s is in alpha testing
                        elif distro == 'k3d':
                            distro += ' [magenta](alpha)[/]'

                        radio_button = RadioButton(distro, value=enabled)
                        # make the radio button cute
                        radio_button.BUTTON_INNER = '♥'

                        yield radio_button

                yield Label(" ")

                yield Label("[b][green]Description[/][/]")
                yield Static(DEFAULT_DISTRO_OPTIONS[DEFAULT_DISTRO]['description'],
                             id='selected-distro-tooltip')
                yield Label(" ")

            # tab 2 - allows selection of different argo cd apps to run in k8s
            with TabPane("Select k8s apps", id="select-apps"):
                full_list = []
                for argocd_app, app_metadata in DEFAULT_APPS.items():
                    full_list.append(Selection(argocd_app.replace("_","-"),
                                               argocd_app,
                                               app_metadata['enabled']))

                with Container(id="select-apps-container"):
                    # top left is the SelectionList of k8s applications
                    yield SelectionList[str](*full_list,
                                             id='selection-list-of-apps')

                    # top right are any input values we need
                    # this is a vertically scrolling container for all the inputs
                    with VerticalScroll(id='app-inputs'):
                        for app, metadata in DEFAULT_APPS.items():
                            secret_keys = metadata['argo'].get('secret_keys', None)
                            app_enabled = metadata['enabled']

                            # if app doesn't have secret keys, continue to next app
                            if not secret_keys:
                                continue
                            # if the app has secret keys
                            else:
                                init = metadata.get('init', False)
                                # if there's no init possible, skip this app
                                if not init:
                                    continue
                                else:
                                    init_enabled = init.get('enabled', False)

                                # make a pretty title for the app to configure
                                s_class = f"app-init-switch-and-label {app}"
                                with Container(classes=s_class):
                                    app_title = app.replace('_', ' ').title()
                                    yield Label(f"[green]{app_title}[/]",
                                                classes=f"{app} app-label")
                                    yield Label("Initialize: ",
                                                classes=f"{app} app-init-switch-label")
                                    yield Switch(value=True,
                                                 classes=f"app-init-switch {app}")
                                yield Label(" ", classes=app)

                                # iterate through the app's secret keys
                                for secret_key, value in secret_keys.items():
                                    secret_label = secret_key.replace("_", " ")
                                    placeholder = "enter a " + secret_label
                                    input_classes = f"app-input {app}"
                                    if value:
                                        app_input = Input(placeholder=placeholder,
                                                          value=value,
                                                          classes=input_classes)
                                    else:
                                        app_input = Input(placeholder=placeholder,
                                                          classes=input_classes)
                                    input_container_class = f"app-label-and-input {app}"

                                    with Horizontal(classes=input_container_class):
                                        yield Label(f"{secret_label}: ",
                                                    classes=f"app-input-label {app}")
                                        if not app_enabled or not init_enabled:
                                            app_input.display = False
                                        yield app_input

                                yield Label(" ", classes=app)


                    with VerticalScroll(id='app-tooltip-container'):
                        # Bottom half of the screen for select-apps TabPane()
                        yield Label("[b][green]Description[/][/]")
                        yield Label("", id='selected-app-tooltip-description')
                        yield Label(" ")

                        yield Label("[b][cornflower_blue]Argo CD App Repository[/][/]")
                        yield Label("", id='selected-app-tooltip-repo')

    def action_show_tab(self, tab: str) -> None:
        """Switch to a new tab."""
        self.get_child_by_type(TabbedContent).active = tab

    def on_mount(self) -> None:
        # screen and header styling
        self.screen.styles.border = ("heavy", "cornflowerblue")
        self.title = "🧸smol k8s lab"
        self.sub_title = "now with more 🦑"

        # styling for the select-apps tab
        cute_question = "ʕ ᵔᴥᵔʔ Select apps to install on k8s"
        self.query_one(SelectionList).border_title = cute_question

        # styling for the select-distro tab
        cute_question2 = "ʕ ᵔᴥᵔʔ Select which Kubernetes distributrion to use"
        self.query_one(RadioSet).border_title = cute_question2

        # styling for the select-distro tab
        cute_question3 = "Configure selected apps ʕᵔᴥᵔ ʔ"
        self.get_widget_by_id('app-inputs').border_title = cute_question3

    @on(Mount)
    @on(SelectionList.SelectedChanged)
    @on(TabbedContent.TabActivated)
    def update_configue_apps_view(self) -> None:
        # get the last item in the list selected items
        selected_items = self.query_one(SelectionList).selected

        # for each application in DEFAULT_APPS
        for application in DEFAULT_APPS.keys():
            # get any objects using this application's name as their class
            app_class_objects = self.query(f".{application}")

            # if the application is in the selected items, set enabled to True
            if application in selected_items:
                enabled = True
            else:
                enabled = False

            # set the DEFAULT_APPS
            DEFAULT_APPS[application]['enabled'] = enabled
            if app_class_objects:
                for app_obj in app_class_objects:
                    app_obj.display = enabled

    @on(SelectionList.SelectionHighlighted)
    def update_selected_app_blurb(self) -> None:
        selection_list = self.query_one(SelectionList)

        # only the highlighted index
        highlighted_idx = selection_list.highlighted

        # the actual highlighted app
        highlighted_app = selection_list.get_option_at_index(highlighted_idx).value

        new_repo, new_blurb = generate_tool_tip(highlighted_app)

        # update the static text with the new app description and repo
        self.get_widget_by_id('selected-app-tooltip-repo').update(new_repo)
        self.get_widget_by_id('selected-app-tooltip-description').update(new_blurb)

    @on(RadioSet.Changed)
    def update_k8s_distro_description(self) -> None:
        pressed_index = self.query_one(RadioSet).pressed_index
        pressed_distro = sorted(DEFAULT_DISTRO_OPTIONS.keys())[pressed_index]
        description = DEFAULT_CONFIG['k8s_distros'][pressed_distro]['description']
        self.get_widget_by_id('selected-distro-tooltip').update(description)


def generate_tool_tip(app_name: str):
    """
    generate tooltip like:
    """
    app_description = DEFAULT_APPS[app_name]['description']

    repo_link = "/".join([DEFAULT_APPS[app_name]['argo']['repo'],
                          'tree',
                          DEFAULT_APPS[app_name]['argo']['ref'],
                          DEFAULT_APPS[app_name]['argo']['path']])

    repo = f"[steel_blue][link={repo_link}]{repo_link}[/link]"

    desc = f"[dim]{app_description}[/dim]"

    return repo, desc



if __name__ == "__main__":
    reply = ConfigureAll().run()
    print(reply)