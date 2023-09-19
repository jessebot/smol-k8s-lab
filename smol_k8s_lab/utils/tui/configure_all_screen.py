#!/usr/bin/env python3.11
from textual import on
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll, Container, Horizontal
from textual.binding import Binding
from textual.events import Mount
from textual.widgets import (Button, Footer, Header, Input, Label,
                             Select, SelectionList, Static, TabbedContent,
                             TabPane)
from textual.widgets._toggle_button import ToggleButton
from textual.widgets.selection_list import Selection
from smol_k8s_lab.constants import (DEFAULT_APPS, DEFAULT_DISTRO,
                                    DEFAULT_DISTRO_OPTIONS, DEFAULT_CONFIG)
from smol_k8s_lab.utils.tui.help_screen import HelpScreen
from smol_k8s_lab.utils.tui.app_config_pane import ArgoCDAppInputs
from smol_k8s_lab.utils.tui.kubelet_config import KubeletConfig


class SmolK8sLabConfig(App):
    """
    Textual app to configure smol-k8s-lab
    """
    CSS_PATH = "./css/configure_all.tcss"
    BINDINGS = [Binding(key="h,?",
                        key_display="h",
                        action="request_help",
                        description="Show Help",
                        show=True),
                Binding(key="q",
                        key_display="q",
                        action="quit",
                        description="Quit smol-k8s-lab")]
    ToggleButton.BUTTON_INNER = '♥'

    def __init__(self, user_config: dict) -> None:
        self.usr_cfg = user_config
        self.previous_app = ''
        super().__init__()

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
            with TabPane("Select Kubernetes distro", id="select-distro"):
                select_prompt = ("[magenta]Select Kubernetes distro from this "
                                 f"dropdown (default: {DEFAULT_DISTRO})")

                # create all distro selection choices for the top of tabbed content
                my_options = tuple(DEFAULT_DISTRO_OPTIONS.keys())
                yield Select(((line, line) for line in my_options),
                             prompt=select_prompt,
                             id="distro-drop-down", allow_blank=False)

                for distro, distro_metadata in DEFAULT_DISTRO_OPTIONS.items():
                    with VerticalScroll(classes=f"k8s-distro-config {distro}"):
                        if distro == DEFAULT_DISTRO:
                            display = True
                        else:
                            display = False

                        # node input row
                        node_class = f"{distro} nodes-input"
                        node_row = Horizontal(classes=f"{node_class}-row")
                        node_row.display = display
                        with node_row:
                            disabled = False
                            if distro == 'k3s':
                                disabled = True

                            # take number of nodes from config and make string
                            nodes = distro_metadata.get('nodes', False)
                            if nodes:
                                control_nodes = str(nodes.get('control_plane', 1))
                                worker_nodes = str(nodes.get('workers', 0))
                            else:
                                control_nodes = "1"
                                worker_nodes = "0"

                            yield Label("control plane nodes:",
                                        classes=f"{node_class}-label")
                            yield Input(value=control_nodes,
                                        placeholder='1',
                                        classes=f"{node_class}-control-input",
                                        disabled=disabled)

                            yield Label("worker nodes:",
                                        classes=f"{node_class}-label")
                            yield Input(value=worker_nodes,
                                        placeholder='0',
                                        classes=f"{node_class}-worker-input",
                                        disabled=disabled)

                        # kubelet config section
                        extra_args = distro_metadata['kubelet_extra_args']
                        kubelet_cf = KubeletConfig(distro, extra_args)
                        kubelet_cf.display = display
                        yield kubelet_cf

                        # take extra k3s args
                        if distro == 'k3s' or distro == 'k3d':
                            k3_class = f"{distro} k3s-config-container"
                            k3_container = Container(classes=k3_class)
                            k3_container.display = display

                            with k3_container:
                                if distro == 'k3s':
                                    k3s_args = distro_metadata['extra_cli_args']
                                else:
                                    k3s_args = distro_metadata['extra_k3s_cli_args']

                                if k3s_args:
                                    k3s_class = f'{distro} k3s-arg'

                                    for arg in k3s_args:
                                        placeholder = "enter an extra arg for k3s"

                                        with Container(classes=f'{k3s_class}-row'):
                                            yield Input(value=arg,
                                                        placeholder=placeholder,
                                                        classes=f"{k3s_class}-input")
                                            yield Button("🚮",
                                                         classes=f"{k3s_class}-del-button")

                                yield Button("➕ Add New Arg",
                                             classes=f"{k3s_class}-add-button")

                with Container(id="k8s-distro-description-container"):
                    description = DEFAULT_DISTRO_OPTIONS[DEFAULT_DISTRO]['description']
                    formatted_description = format_description(description)
                    yield Static(f"{formatted_description}",
                                 id='k8s-distro-description')

            # tab 2 - allows selection of different argo cd apps to run in k8s
            with TabPane("Select Applications", id="select-apps"):
                full_list = []
                for app, app_meta in DEFAULT_APPS.items():
                    item = Selection(app.replace("_","-"), app, app_meta['enabled'])
                    full_list.append(item)

                selection_list = SelectionList[str](*full_list,
                                                    id='selection-list-of-apps')

                # top of the screen in second tab
                with Container(id="select-apps-container"):
                    # top left: the SelectionList of k8s applications
                    yield selection_list

                    # top right: vertically scrolling container for all inputs
                    with VerticalScroll(id='app-inputs-pane'):
                        for app, metadata in DEFAULT_APPS.items():
                            id_name = app.replace("_", "-") + "-inputs"
                            single_app_inputs_container = Container(id=id_name)
                            single_app_inputs_container.display = False
                            with single_app_inputs_container:
                                yield ArgoCDAppInputs(app, metadata)

                    # Bottom half of the screen for select-apps TabPane()
                    with VerticalScroll(id="app-description-container"):
                        yield Label("", id="app-description")

    def action_show_tab(self, tab: str) -> None:
        """Switch to a new tab."""
        self.get_child_by_type(TabbedContent).active = tab

    def on_mount(self) -> None:
        # screen and header styling
        self.title = "ʕ ᵔᴥᵔʔ smol k8s lab"
        self.sub_title = "now with more 🦑"

        node_rows = self.query("nodes-input-row")
        for row in node_rows:
            row.border_title = "Adjust how many of each node type to deploy"

        # styling for the select-apps tab - select apps container - left
        select_apps_title = "[green]Select apps"
        self.query_one(SelectionList).border_title = select_apps_title

        # styling for the select-distro tab - middle
        distro_desc = self.get_widget_by_id("k8s-distro-description-container")
        distro_desc.border_title = "[white]Distro Description[/]"

        app_desc = self.get_widget_by_id("app-description-container")
        app_desc.border_title = "[white]App Description[/]"

    @on(Mount)
    @on(SelectionList.SelectedChanged)
    @on(SelectionList.SelectionHighlighted)
    @on(TabbedContent.TabActivated)
    def update_selected_app_blurb(self) -> None:
        selection_list = self.query_one(SelectionList)

        # only the highlighted index
        highlighted_idx = selection_list.highlighted

        # the actual highlighted app
        highlighted_app = selection_list.get_option_at_index(highlighted_idx).value

        # update the bottom app description to the highlighted_app's description
        blurb = format_description(DEFAULT_APPS[highlighted_app]['description'])
        self.get_widget_by_id('app-description').update(blurb)

        # styling for the select-apps tab - configure apps container - right
        app_title = highlighted_app.replace("_", "-")
        app_cfg_title = f"⚙️ [green]Configure initial params for [magenta]{app_title}"
        self.get_widget_by_id("app-inputs-pane").border_title = app_cfg_title

        if self.previous_app:
            dashed_app = self.previous_app.replace("_","-")
            app_input = self.get_widget_by_id(f"{dashed_app}-inputs")
            app_input.display = False

        dashed_app = highlighted_app.replace("_","-")
        app_input = self.get_widget_by_id(f"{dashed_app}-inputs")
        app_input.display = True

        self.previous_app = highlighted_app

    @on(Select.Changed)
    def update_k8s_distro_description(self, event: Select.Changed) -> None:
        """
        change the description text in the bottom box for k8s distros
        """
        distro = str(event.value)
        desc = format_description(DEFAULT_CONFIG['k8s_distros'][distro]['description'])
        self.get_widget_by_id('k8s-distro-description').update(desc)

        for default_distro_option in DEFAULT_DISTRO_OPTIONS.keys():
            # get any objects using this distro's name as their class
            distro_class_objects = self.query(f".{default_distro_option}")

            if default_distro_option == distro:
                enabled = True
            else:
                enabled = False

            # change display to True if the distro is selected, else False
            if distro_class_objects:
                for distro_obj in distro_class_objects:
                    distro_obj.display = enabled

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """
        get pressed button and act on it
        """
        button_classes = event.button.classes

        # lets you delete a k3s-arg row
        if "k3s-arg-del-button" in button_classes:
            parent_row = event.button.parent
            parent_row.remove()

        # lets you add a new k3s config row
        if "k3s-arg-add-button" in button_classes:
            parent_container = event.button.parent
            placeholder = "enter an extra arg for k3s"
            parent_container.mount(Horizontal(
                Input(placeholder=placeholder, classes="k3s-arg-input"),
                Button("🚮", classes="k3s-arg-del-button"),
                classes="k3s-arg-row"
                ), before=event.button)

    def action_request_help(self) -> None:
        """
        if the user presses 'h' or '?', show the help modal screen
        """
        self.push_screen(HelpScreen())


def format_description(description: str):
    """
    change description to dimmed colors
    links are changed to steel_blue and not dimmed
    """
    description = description.replace("[link", "[/dim][steel_blue][link")
    description = description.replace("[/link]", "[/link][/steel_blue][dim]")

    return f"""[dim]{description}[/dim]"""


if __name__ == "__main__":
    # this is temporary during testing
    from smol_k8s_lab.constants import INITIAL_USR_CONFIG
    reply = SmolK8sLabConfig(INITIAL_USR_CONFIG).run()
    print(reply)
