#!/usr/bin/env python3.11
# internal library
from smol_k8s_lab.tui.validators.already_exists import CheckIfNameAlreadyInUse

# external libraries
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.suggester import SuggestFromList
from textual.validation import Length
from textual.widgets import Input, Button, Label


KUBELET_SUGGESTIONS = SuggestFromList((
        "podsPerCore",
        "maxPods",
        "node-labels",
        "featureGates"
        ))


NETWORKING_SUGGESTIONS = SuggestFromList((
        "apiServerPort",
        "apiServerAddress",
        "disableDefaultCNI",
        "ipFamily",
        "kubeProxyMode",
        "podSubnet",
        "serviceSubnet"
        ))


K3S_SUGGESTIONS = SuggestFromList((
       "disable",
       "disable-network-policy",
       "flannel-backend",
       "secrets-encryption",
       "node-label",
       "kubelet-arg",
       "datastore-endpoint",
       "etcd-s3",
       "server",
       "debug",
       "cluster-domain"
       "token",
       "agent-token",
       "bind-address",
       "cluster-dns",
       "https-listen-port",
       "kube-proxy-arg",
       "log",
       "rootless"
       ))


def placeholder_grammar(key: str) -> str:
    """
    generates a grammatically correct placeolder string for inputs
    """
    article = ""

    # check if this is a plural (ending in s) and if ip address pool
    plural = key.endswith('s') or key == "address_pool"
    if plural:
        plural = True

    # check if the key starts with a vowel
    starts_with_vowel = key.startswith(('o','a','e'))

    # create a gramatically corrrect placeholder
    if starts_with_vowel and not plural:
        article = "an"
    elif not starts_with_vowel and not plural:
        article = "a"

    # if this is plural change the grammar accordingly
    if plural:
        return f"Please enter a comma seperated list of {key}"
    else:
        return f"Please enter {article} {key}"


def create_sanitized_list(input_value: str) -> list:
    """
    take string and split by , or ' ' if there are any in it. returns list of
    items if no comma or space in string, returns list with string as only index
    """

    # split by comma, thereby generating a list from a csv
    if "," in input_value:
        input_value = input_value.replace(" ","")
        value = input_value.split(",")

    # split by spaces, thereby generating a list from a space delimited list
    elif "," not in input_value and " " in input_value:
        value = input_value.split(" ")

    # otherwise just use the value
    else:
        value = [input_value]

    return value


class NewOptionModal(ModalScreen):
    BINDINGS = [Binding(key="b,q,escape",
                        key_display="esc",
                        action="app.pop_screen",
                        description="Cancel")]

    CSS_PATH = [
            "./css/base_modal.tcss",
            "./css/new_option_modal.tcss"
            ]

    def __init__(self, trigger: str, in_use_args: list = []) -> None:
        self.in_use_args = in_use_args
        self.trigger = trigger
        super().__init__()

    def compose(self) -> ComposeResult:
        # base screen grid
        question = f"[#ffaff9]Add[/] [i]new[/] [#C1FF87]{self.trigger} option[/]."
        tooltip = (
                "Start typing an option to show suggestions. Use the right arrow "
                "key to complete the suggestion. Hit enter to submit."
                )
        if self.trigger.startswith("k3"):
            tooltip += (
                    "Note: If [dim][#C1FF87]cilium[/][/] is [i]enabled[/], we "
                    "add flannel-backend: none and disable-network-policy: true."
                )
            suggestions = K3S_SUGGESTIONS
        elif "network" in self.trigger:
            tooltip += ("Note: If [dim][#C1FF87]cilium[/][/] is [i]enabled[/],"
                        "we pass in disableDefaultCNI=true.")
            suggestions = NETWORKING_SUGGESTIONS
        elif "kubelet" in self.trigger:
            suggestions = KUBELET_SUGGESTIONS

        with Grid(id="new-option-modal-screen"):
            # grid for app question and buttons
            with Grid(id="question-box"):
                yield Label(question, id="modal-text")

                with Grid(id='new-option-grid'):
                    input = Input(id='new-option-input',
                                  placeholder=f"new {self.trigger} option",
                                  suggester=suggestions,
                                  validators=[
                                      Length(minimum=4),
                                      CheckIfNameAlreadyInUse(self.in_use_args)
                                      ]
                                  )
                    input.tooltip = tooltip
                    yield input

                    button = Button("➕ add option", id="add-button")
                    button.disabled = True
                    yield button

    def on_mount(self) -> None:
        box = self.get_widget_by_id("question-box")
        box.border_subtitle = "[@click=app.pop_screen]cancel[/]"

    @on(Input.Changed)
    @on(Input.Submitted)
    def disable_button_or_not(self, event: Input.Changed | Input.Submitted) -> None:
        add_button = self.get_widget_by_id("add-button")

        # disable the button if the input is invalid
        if event.validation_result.is_valid:
            add_button.disabled = False
        else:
            if "already in use" in event.validation_result.failure_descriptions[0]:
                res = ("That option is already defined! If you want to add additional"
                       f"options to {event.input.value}, you can use a comma "
                       "seperated list.")
                self.app.notify(res,
                                title="Input Validation Error", severity="error",
                                timeout=9)
            add_button.disabled = True

        # if button is currently enabled and the user presses enter, press button
        if isinstance(event, Input.Submitted):
            if not add_button.disabled:
                add_button.action_press()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """
        get pressed button and act on it
        """
        input = self.get_widget_by_id("new-option-input")
        self.dismiss(input.value)


def format_description(description: str = ""):
    """
    change description to dimmed colors
    links are changed to steel_blue and not dimmed
    """
    if not description:
        description = "No Description provided yet for this user defined application."

    description = description.replace("[link", "[steel_blue][link")
    description = description.replace("[/link]", "[/link][/steel_blue]")

    return f"""{description}"""