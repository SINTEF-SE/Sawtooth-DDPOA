#!/usr/bin/env python3
import asyncio
import time

import iterm2
from kubernetes import client, config

tabs = []


def get_commands():
    commands = []
    command = "/usr/local/bin/kubectl logs -f {} -c sawtooth-dpos-engine"
    # Configs can be set in Configuration class directly or using helper utility
    config.load_kube_config()

    v1 = client.CoreV1Api()
    ret = v1.list_pod_for_all_namespaces(watch=False)
    for i in ret.items:
        if i.metadata.namespace == "default":
            for c in i.spec.containers:
                if c.name == "sawtooth-dpos-engine":
                    commands.append(command.format(i.metadata.name))

    return commands


async def show_logs_in_tab(window, commands):
    for idx, c in enumerate(commands):
        print("[+] Displaying logs for pod %d" % idx)
        t = await window.async_create_tab(command=c, profile="Guillaume - Solarized")
        if t is not None:
            tabs.append(t.tab_id)
            await t.async_set_title("Pod %d" % idx)

    await window.async_activate()


async def main(connection):
    print("[+] Using iTerm2")
    app = await iterm2.async_get_app(connection)

    await app.async_activate()

    window = app.current_window
    if window is not None:
        commands = get_commands()
        await show_logs_in_tab(window, commands)
    else:
        print("No current window")


async def terminate_tabs(connection):
    app = await iterm2.async_get_app(connection)
    window = app.current_window
    if window is not None:
        for tab in window.tabs:
            if tab.tab_id in tabs:
                title = (await tab.async_get_variable("titleOverride"))
                print("[*] Closing tab for %s..." % title)
                await tab.async_close(force=True)
    else:
        print("No current window")
    print("[+] Done")

try:
    # Starting iTerm if not started already
    bundle = "com.googlecode.iterm2"
    if not AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_(bundle):
        AppKit.NSWorkspace.sharedWorkspace().launchApplication_("iTerm")

    iterm2.run_forever(main)
except KeyboardInterrupt:
    iterm2.run_until_complete(terminate_tabs)