#!/bin/bash
###############################################################
# SPDX-License-Identifier: BSD-2-Clause-Patent
# Copyright (c) 2020 Tomer Eliyahu (Intel)
# This code is subject to the terms of the BSD+Patent license.
# See LICENSE file for more details.
###############################################################

scriptdir="$(cd "${0%/*}" && pwd)"
rootdir=$(realpath "$scriptdir/../../")

# shellcheck source=../../tools/functions.sh
. "$rootdir/tools/functions.sh"

# shellcheck source=./owncloud_definitions.sh
. "$scriptdir/owncloud_definitions.sh"


usage() {
    echo "usage: $(basename "$0") [-hv] <user> <password> <remote-path> <local-path>"
    echo "  options:"
    echo "      -h|--help - display this help."
    echo "      -v|--verbose - enable verbosity"
    echo "      -u|--url - webDAV URL (default https://ftp.essensium.com/owncloud/remote.php/dav/files/USERNAME)"
    echo
    echo "  positional arguments:"
    echo "      remote-path - path in the cloud, relative to the user home to upload"
    echo "      local-path - local file or folder to upload"
    echo ""
    echo "  Credentials are taken from $HOME/.netrc"
    echo "  Make sure it has a line like this:"
    echo "    machine ftp.essensium.com login <user> password <password>"
    echo ""
}


main() {
    if ! OPTS=$(getopt -o 'hvu:' --long help,verbose,url: -n 'parse-options' -- "$@"); then
        echo echo "Failed parsing options." >&2; usage; exit 1
    fi

    eval set -- "$OPTS"

    while true; do
        case "$1" in
            -h | --help)            usage; exit 0;;
            -v | --verbose)         export VERBOSE=true; QUIET=; shift;;
            -u | --owncloud-url)    OWNCLOUD_URL="$2"; shift 2;;
            -- ) shift; break ;;
            * ) err "unsupported argument $1"; usage; exit 1;;
        esac
    done

    [ -n "$1" ] || { usage; err "Missing remote-path"; exit 1; }
    remote_path="$1"; shift
    [ -n "$1" ] || { usage; err "Missing local-path"; exit 1; }
    local_path="$1"; shift

    info "upload $local_path to $remote_path at $OWNCLOUD_URL (using user $user)"

    if ! command -v uuidgen > /dev/null ; then
        err "You need uuidgen to use this script. Please install it and try again."
        exit 1
    fi

    # We'll group uploads in the following directory in the user home
    # we don't care if create_dir fails because it may already exist:
    create_dir "temp_uploads" > /dev/null 2>&1

    remote_temp_path="temp_uploads/$(uuidgen)"
    create_dir "$remote_temp_path"

    info "Using temporary path $remote_temp_path"

    status=0

    if ! find "$local_path" -type d -exec \
            realpath {} --relative-to="$(dirname "$local_path")" \; | {
                error=0
                while read -r -s dir; do
                    printf . # show progress
                    create_dir "$remote_temp_path/$dir" || {
                        error="$?"
                        continue
                    }
                    printf . # show progress
                    # get the list of files to upload in the format <file>,<file>,...,<file>
                    files=$(find "$(dirname "$local_path")/$dir/" -type f -maxdepth 1 -print0 | tr '\0' ',' | sed 's/,$//')
                    dbg "$files"
                    [ -n "$files" ] && {
                        upload_files "$remote_temp_path/$dir" "$files" || {
                            error="$?"
                        }
                    }
                done
                return $error
            }
    then
        echo
        err "Uploading to a temporary directory failed!"
        status=1
    else
        success "Uploading to a temporary directory succeeded!"
    fi
    echo

    info "Moving the temporary directory $remote_temp_path to $remote_path"
    move "$remote_temp_path" "$remote_path" || {
        status="$?"
    }

    return "$status"
}

QUIET=true

main "$@"