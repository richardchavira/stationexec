# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import socket

import simplejson
from stationexec.logger import log
from tornado import httpclient

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse


def check_if_client_available(host, port):
    online = False
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))
        online = True
    except socket.error:
        online = False
    finally:
        s.close()
    return online


def http_get(url, body, decode_json=False, configurations=None):
    return _http_request("GET", url, body, decode_json, configurations)


def http_post(url, body, decode_json=False, configurations=None):
    return _http_request("POST", url, body, decode_json, configurations)


def _http_request(method, url, body, decode_json, configurations, timeout=20):
    """

    :param method:
    :param url:
    :param body:
    :param decode_json:
    :param configurations:
    :param timeout:
    :return:
    """
    headers = {}

    configurations["method"] = method
    configurations["conect_timeout"] = timeout
    configurations["request_timeout"] = timeout
    if body:
        configurations['body'] = body
        headers['Content-Type'] = 'application/json'
    else:
        headers['Content-Type'] = 'text/html'
        headers['Content-Length'] = '0'

    http_client = httpclient.HTTPClient()

    response = None
    try:
        http_response = http_client.fetch(url, headers=headers, **configurations)
        response_code = http_response.code
    except httpclient.HTTPError as e:
        # HTTPError is raised for non-200 responses; the response
        # can be found in e.response.
        response_code = e.code
    except Exception as e:
        # Other errors are possible, such as IOError.
        log.exception("HTTP request exception", e)
        raise
    else:
        if http_response.body:
            response = http_response.body
            if decode_json and len(response) > 0:
                try:
                    response = simplejson.loads(response)
                except Exception:
                    raise IOError('JSON decoding error on ' + str(response))
    finally:
        http_client.close()

    return response, response_code


def _parse_url(url):
    if not url.startswith("http"):
        url = "http://{0}".format(url)

    parsed_url = urlparse(url)
    host = parsed_url.netloc
    port = parsed_url.port
    if port is None:
        port = 80

    return host, port


def http10_get(url, body="", decode_json=False):
    return _http10_request("GET", url, body, decode_json)


def http10_post(url, body="", decode_json=False):
    return _http10_request("POST", url, body, decode_json)


def _http10_request(method, url, body, decode_json):
    """
    Build and send a request to a HTTP/1.0 server

    :param method:
    :param url: Full path of where to connect (include HTTPx prefix and port number)
    :param body:
    :param decode_json:
    :return:
    """
    host, port = _parse_url(url)
    # Assume that the body is JSON data if it exists
    content_type = "application/json" if len(body) > 0 else "text/html"

    # Manually build the HTTP 1.0 message, appending body (which may not have content)
    msg = "{0} {1} HTTP/1.0\r\nContent-Length: {2}\r\nHost: {3}\r\nContent-Type: {4}\r\nConnection: Close\r\n\r\n{5}". \
        format(method, url, len(body), host, content_type, body)

    # Connect to server socket, send message, and retrieve response
    # All connection exceptions allowed to bubble out for user to catch
    http_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        http_sock.connect((host, port))
        http_sock.sendall(msg)
        rmsg = http_sock.recv(1024)
    finally:
        http_sock.close()

    # Attempt to parse the response - parsing on a malformed response will most
    # likely result in an exception
    response_code = None
    response_body = None
    if len(rmsg) > 0:
        crlf = rmsg.find('\r\n')
        header = rmsg[0:crlf]
        head = header.split()
        response_code = int(head[1])

        crlf = rmsg.find('\r\n\r\n')
        response_body = rmsg[crlf + 4:]

    # If desired, attempt to decode the response body as JSON - parsing errors
    # allowed to bubble up
    if decode_json and response_body is not None:
        response_body = simplejson.loads(response_body)

    return response_body, response_code
