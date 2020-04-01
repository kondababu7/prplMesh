#!/bin/bash

scriptdir="$(cd "${0%/*}" && pwd)"
rootdir=$(realpath "$scriptdir/../../")

# shellcheck source=../tools/functions.sh
. "$rootdir/tools/functions.sh"


create_dir() {
    # create dir $1 in $OWNCLOUD_URL/$user/.
    # if $2 is true, try to delete any existing dir first.
    #
    # note: parent directories are not created automatically, so make sure
    #       to create them if they don't exist yet.
    #
    # uses:
    #   OWNCLOUD_URL
    #   user
    local dir delete status
    dir="$1"
    delete="$2"
    status=0

    dbg "Create directory: $dir"
    if [ "$delete" = true ] ; then
        curl ${QUIET:+-s -S} -f -n -X DELETE "$OWNCLOUD_URL/$user/$dir" > /dev/null 2>&1
    fi
    curl ${QUIET:+ -s -S} -f -n -X MKCOL "$OWNCLOUD_URL/$user/$dir" || {
        status="$?"
        err "Failed to create dir: $dir (error $status)"
    }
    return "$status"
}

upload_files() {
    # Upload files given as arguments.
    # $1 the directory to upload to (make sure it exists already).
    # $2 the files to upload, comma separated.
    # uses:
    #
    #   OWNCLOUD_URL
    #   user
    local dir files status
    dir="$1"
    files="$2"
    status=0

    curl ${QUIET:+ -s -S} -f -n -T "{$files}" "$OWNCLOUD_URL/$user/$dir/" || {
        status="$?"
        err "Failed to upload files to $dir (error $status)"
    }
    return "$status"
}

move() {
    # move $1 to $2 on remote.
    # if $2 already exists, it's completely overwritten.
    #
    # uses:
    #   OWNCLOUD_URL
    #   user
    local src dst status
    src="$1"
    dst="$2"
    status=0
    dbg "Moving \"$src\" to \"$dst\" on the remote"
    curl ${QUIET:+-s -S} -f -n -X MOVE --header \
         "Destination: $OWNCLOUD_URL/$user/$dst" "$OWNCLOUD_URL/$user/$src" || {
        status="$?"
        err "Failed to move $src to $dst (error $status)"
    }
    return "$status"
}

copy() {
    # copy $1 to $2 on remote.
    # if $2 already exists, it's completely overwritten.
    #
    # uses:
    #   OWNCLOUD_URL
    #   user
    local src dst status
    src="$1"
    dst="$2"
    status=0
    dbg "Copying \"$src\" to \"$dst\" on the remote"
    curl ${QUIET:+-s -S} -f -n -X COPY --header "Destination: $OWNCLOUD_URL/$user/$dst" "$OWNCLOUD_URL/$user/$src" || {
        status="$?"
        err "Failed to copy $src to $dst (error $status)"
    }
    return "$status"
}

OWNCLOUD_URL="https://ftp.essensium.com/owncloud/remote.php/dav/files"
user=$(awk '/ftp.essensium.com/{getline; print $4}' ~/.netrc)

if [ ! "$#" = 0 ] ; then
    "$@"
fi