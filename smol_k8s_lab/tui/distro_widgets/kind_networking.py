#!/usr/bin/env python3.11
from textual import on
from textual.app import ComposeResult
from textual.containers import VerticalScroll, Grid
from textual.suggester import SuggestFromList
from textual.validation import Length
from textual.widget import Widget
from textual.widgets import Input, Button, Label


VALUE_SUGGESTIONS = SuggestFromList(("true", "ipv4", "ipv6"))
HELP_TEXT = (
        "Add key value pairs to [steel_blue][link="
        "https://kind.sigs.k8s.io/docs/user/configuration/#networking]"
        "kind networking config[/][/]."
        )


class KindNetworkingConfig(Widget):
    """
    Container for extra args for kind networking configuration
    """

    def __init__(self, kind_neworking_params: list = []) -> None:
        self.kind_neworking_params = kind_neworking_params
        super().__init__()

    def compose(self) -> ComposeResult:
        with Grid(id="kind-networking-container"):
            yield Label(HELP_TEXT, classes="help-text")
            yield VerticalScroll(id="kind-networking-config-scroll")

    def on_mount(self) -> None:
        if self.kind_neworking_params:
            for key, value in self.kind_neworking_params.items():
                self.generate_row(key, str(value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """
        get pressed button add or delete button and act on it
        """
        parent_row = event.button.parent
        input_key = parent_row.children[1].name
        parent_yaml = self.app.cfg['k8s_distros']['kind']['networking_args']
        if input_key and parent_yaml.get(input_key, False):
            parent_yaml.pop(input_key)
            self.app.write_yaml()
        parent_row.remove()

    @on(Input.Submitted)
    @on(Input.Changed)
    def update_base_yaml(self, event: Input.Changed | Input.Submitted) -> None:
        if event.validation_result.is_valid:
            # grab the user's yaml file from the parent app
            extra_args = self.app.cfg['k8s_distros']['kind']['networking_args']

            # if they answer with a boolean, make sure it's written out correctly
            if event.input.value.lower() == 'true':
                extra_args[event.input.name] = True
            elif event.input.value.lower() == 'false':
                extra_args[event.input.name] = False
            else:
                extra_args[event.input.name] = event.input.value

            self.app.write_yaml()

    def generate_row(self, param: str = "", value: str = "") -> Grid:
        """
        generate a new input field set
        """
        # base class for all the below object
        row_class = "kind-networking-input"

        # label for input field
        label = Label(param.replace("_", " ") + ":", classes="input-label")

        # second input field
        param_value_input_args = {"classes": f"{row_class}-value",
                                  "placeholder": "kind networking param value",
                                  "suggester": VALUE_SUGGESTIONS,
                                  "validators": Length(minimum=1),
                                  "name": param}
        if value:
            param_value_input_args["value"] = value
        param_value_input = Input(**param_value_input_args)

        # delete button for each row
        del_button = Button("🚮", classes=f"{row_class}-del-button")
        del_button.tooltip = "Delete this kind networking parameter"

        self.get_widget_by_id("kind-networking-config-scroll").mount(
                Grid(label, param_value_input, del_button,
                     classes="label-input-delete-row")
                )