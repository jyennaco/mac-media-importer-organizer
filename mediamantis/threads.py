"""
mediamantis.threads
~~~~~~~~~~~~~~~~~~~
Multithreading utilities.

"""

import logging
from pycons3rt3.logify import Logify
from .mantistypes import chunker

mod_logger = Logify.get_name() + '.threads'


def process_threads(threads, max_simultaneous_threads):
    """Process groups of threads in chunks

    :param threads: (list) of threading.Thread objects
    :param max_simultaneous_threads: (int) Maximum number of threads to run simultaneously
    :return: None
    """
    log = logging.getLogger(mod_logger + '.process_threads')

    # Start threads in groups
    thread_group_num = 1
    log.info('Starting threads in groups of: {n}'.format(n=str(max_simultaneous_threads)))
    for thread_group in chunker(threads, max_simultaneous_threads):
        log.info('Starting thread group: {n}'.format(n=str(thread_group_num)))
        for thread in thread_group:
            thread.start()
        log.info('Waiting for completion of thread group: {n}'.format(n=str(thread_group_num)))
        for t in thread_group:
            t.join()
        log.info('Completed thread group: {n}'.format(n=str(thread_group_num)))
        thread_group_num += 1
    log.info('Completed processing all thread groups')
