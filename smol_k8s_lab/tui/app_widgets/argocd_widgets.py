#!/usr/bin/env python3.11
from smol_k8s_lab.tui.util import create_sanitized_list
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.validation import Length
from textual.widgets import Input, Label, Static


ARGO_TOOLTIPS = {'repo': 'URL to a git repository where you have k8s manifests ' + \
                         '(including Argo resources) to deploy',
                 'path': 'Path in a git repo to resources you want to deploy. ' +
                         'Trailing slash is important.',
                 'ref': 'Git branch or tag to point to in the repo.',
                 'namespace': 'Kubernetes namespace to deploy the Argo CD App in.'}


class ArgoCDApplicationConfig(Static):

    def __init__(self, app_name: str, argo_params: dict) -> None:
        self.app_name = app_name
        self.argo_params = argo_params
        super().__init__()

    def compose(self) -> ComposeResult:
        help_text = (
                "[link=https://argo-cd.readthedocs.io/en/stable/user-guide/directory/]"
                "Argo CD Application Configuration[/]"
                )

        # Label on the top 
        argo_app_label = Label(help_text, classes=f"{self.app_name} argo-config-header")
        argo_app_label.tooltip = (
                "Configure parameters for an Argo CD Application. Designed "
                "to accomadate [i]directory-type[/] applications. Click for "
                "more info.")
        yield argo_app_label

        for key, value in ARGO_TOOLTIPS.items():
            input = Input(placeholder=f"Please enter a {key}",
                          value=self.argo_params[key],
                          name=key,
                          validators=[Length(minimum=2)],
                          id=f"{self.app_name}-{key}",
                          classes=f"{self.app_name} argo-config-input")
            input.validate(self.argo_params[key])

            argo_label = Label(f"{key}:",
                               classes=f"{self.app_name} argo-config-label")
            argo_label.tooltip = value

            yield Horizontal(argo_label, input,
                             classes=f"{self.app_name} argo-config-row")

    @on(Input.Changed)
    def update_base_yaml(self, event: Input.Changed) -> None:
        input = event.input
        parent_app_yaml = self.app.cfg

        parent_app_yaml['apps'][self.app_name]['argo'][input.name] = input.value

        self.app.write_yaml()


class ArgoCDProjectConfig(Static):

    def __init__(self, app_name: str, argo_params: dict) -> None:
        self.app_name = app_name
        self.argo_params = argo_params
        super().__init__()

    def compose(self) -> ComposeResult:
        # row for project destination namespaces
        with Horizontal(classes=f"{self.app_name} argo-config-row"):
            label = Label("namespaces:",
                          classes=f"{self.app_name} argo-config-label")
            label.tooltip = "Comma seperated list of namespaces"
            yield label

            n_spaces = self.argo_params["destination"]["namespaces"]
            if n_spaces:
                value = ", ".join(n_spaces)
            else:
                value = ""

            classes = f"{self.app_name} argo-config-input argo-proj-ns"
            yield Input(placeholder="Enter comma seperated list of namespaces",
                        name="namespaces",
                        validators=Length(minimum=2),
                        value=value,
                        classes=classes)

        # row for project source repos
        with Horizontal(classes=f"{self.app_name} argo-config-row"):
            label = Label("source repos:",
                          classes=f"{self.app_name} argo-config-label")
            label.tooltip = "Comma seperated list of project source repos"
            yield label

            repos = self.argo_params["source_repos"]
            if repos:
                value = ", ".join(repos)
            else:
                value = ""
            classes = f"{self.app_name} argo-config-input argo-proj-repo"
            yield Input(placeholder="Please enter source repos",
                        value=value,
                        name="source_repos",
                        validators=Length(minimum=5),
                        classes=classes)

    @on(Input.Changed)
    def update_base_yaml(self, event: Input.Changed) -> None:
        """ 
        if the input is valid, write the input as a list to the base yaml
        """
        if event.validation_result.is_valid:
            # section of the yaml this widget updates
            project_yml = self.app.cfg['apps'][self.app_name]['argo']['project']

            # sorts out any spaces or commas as delimeters to create a list
            yaml_value = create_sanitized_list(event.input.value)

            if event.input.name == 'namespaces':
                project_yml['destination'][event.input.name] = yaml_value
            else:
                project_yml[event.input.name] = yaml_value
            self.app.write_yaml()
