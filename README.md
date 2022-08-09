# K8s Homelab

Under construction, but this is where we'll throw some local k8s (kubernetes) testing tools. Currently supported k8s distros, biasing towards small and quick distros:

|             Distro               | K8s Homelab Status              |
|----------------------------------|---------------------------------|
|[k3s](https://k3s.io/)            | in progress - beta              |
|[KinD](https://kind.sigs.k8s.io/) | in progress - beta              |
|[k0s](https://k0sproject.io/)     | in progress - alpha coming soon |

# Quickstart

#### Pre-Req

- Install [k9s](https://k9scli.io/topics/install/), which is like `top` for kubernetes clusters, to monitor the cluster.
- Have internet access.

## Choose a k8s distro 
  
<details>
  <summary>K3s - (Best for Linux on metal or a bridged VM)</summary>

  ```bash
    # this export can also be set in a .env file in the same dir
    export EMAIL="youremail@coolemailfordogs.com"

    # From the cloned repo dir, This should set up k3s and dependencies
    # Will also launch k9s, like top for k8s, To exit k9s, use type :quit
    ./k8s_homelab/k3s/quick-start-k3s.sh
  ```

  #### Ready to clean up this cluster?
  To delete the whole cluster, the above k3s install also included an uninstall script that should be in your path already:

  ```bash
    k3s-uninstall.sh
  ```

</details>

<details>
  <summary>KinD - (Best path for non-prod testing across linux and macOS)</summary>

  ```bash
    # this export can also be set in a .env file in the same dir
    export EMAIL="youremail@coolemailfordogs.com"

    # From the cloned repo dir, This should set up KinD for you
    # Will also launch k9s, like top for k8s, To exit k9s, use type :quit
    ./k8s_homelab/kind/quick-start-kind.sh
  ```

  #### Ready to clean up this cluster?
  To delete the whole cluster, run:

  ```bash
    kind delete cluster
  ```

</details>

<details>
  <summary>K0s - (thing max is working on)</summary>

  Still being developed, but will probably look something like....

  ```bash
    # this export can also be set in a .env file in the same dir
    export EMAIL="youremail@coolemailfordogs.com"
    
    # From the cloned repo dir, This should set up KinD for you
    # Will also launch k9s, like top for k8s, To exit k9s, use type :quit
    ./k8s_homelab/k0s/quick-start-k0s.sh
  ```

  #### Ready to clean up this cluster?
  To delete the whole cluster, run:

  ```bash
    ???
  ```

</details>

## Final Touches

### Port Forwarding
This would forward your app, running on port 80 to 8080 locally, so you can go to http://127.0.0.1:8080/ in your browser

```bash
kubectl port-forward $POD_NAME 80:8080
```

After this, if you want to access this outside of port forwarding to test, you'll need to make sure your app's ingress is setup correctly and then you'll need to setup your router to port forward 80->80 and 443->443 for your WAN. then setup DNS for your domain if you want the wider internet to access this remotely.

## SSL

After SSL is working (if it's not, follow the steps in the [cert-manager common error troubleshooting guide](https://cert-manager.io/docs/faq/acme/#common-errors)), you can also change the `letsencrypt-staging` value to `letsencrypt-prod` for any certs you've installed. 


## Remote cluster administration

You can also copy your remote k3s kubeconfig with a little script in `k3s/`:

```bash
# CHANGE THESE TO YOUR OWN DETAILS or not ¯\_(ツ)_/¯
export REMOTE_HOST="192.168.20.2"
export REMOTE_SSH_PORT="22"
export REMOTE_USER="cooluser4dogs"

# this script will totally wipe your kubeconfig :) use with CAUTION
./k3s/get-remote-k3s-yaml.sh
```

---

# Other Notes

Check out the [./optional](./optional) directory for notes on specific apps, e.g. for postgres on k8s notes, go to [./optional/postgres/README.md].

## Helpful links
- The k3s knowledge here is in this [kauri.io self hosting guide](https://kauri.io/#collections/Build%20your%20very%20own%20self-hosting%20platform%20with%20Raspberry%20Pi%20and%20Kubernetes/%2838%29-install-and-configure-a-kubernetes-cluster-w/) is invaluable. Thank you kauri.io.

- This [encrypted secrets in helm charts guide](https://www.thorsten-hans.com/encrypted-secrets-in-helm-charts/) isn't the guide we need, but helm secrets need to be stored somewhere, and vault probably makes sense

## Troubleshooting hellish networking issues with coredns
Can your pod not get out to the internet? Well, first verify it with this:
```bash
kubectl run -it --rm --image=infoblox/dnstools:latest dnstools
```

Check the `/etc/resolv.conf` and `/etc/hosts` that's been provided by coredns from that pod with:
```bash
cat /etc/resolv.conf
cat /etc/hosts

# also check if this returns google's info correct
# cross check this with a computer that can hit google.com with no issues
host google.com
```

If it doesn't return google.com's info, you should first go read this [k3s issue](https://github.com/k3s-io/k3s/issues/53) (yes, it's present in KIND as well).

Then decide, "*does having subdomains on my LAN spark joy?*"

#### Yes it sparks joy
And then update your `ndot` option in your `/etc/resolv.conf` for podDNS to be 1. You can do this in a deployment. You should read this [k8s doc](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/#pod-dns-config) to learn more. The search domain being more than 1-2 dots deep seems to cause all sorts of problems. Asus in particular is terrible about this. You can test the `resolv.conf` with the infoblox/dnstools docker image from above. It already has the `vi` text editor, which will allow you to quickly iterate.

#### No, it does not spark joy
STOP USING SUBDOMAINS ON YOUR LOCAL ROUTER. Get a pihole and use it for both DNS and DHCP.


## Prometheus notes
Coming soon. Below is kinda broken stuff, that doesn't lead you anywhere:
```bash
# install the repo and search it
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts

# View the chart details
helm show chart prometheus-community/prometheus

# Installation of important charts
helm install prometheus prometheus-community/prometheus
```

## Installing cmctl, the cli tool for cert-manager
You'll need to download the tar ball for your OS [here](https://github.com/cert-manager/cert-manager/releases) and then untar it, and move it into a directory in your `$PATH`. MacOS will fail the first time you run it, and you'll need to go into System Preferences > Security & Privacy > Allow apps downloaded from, to allow an exception.
