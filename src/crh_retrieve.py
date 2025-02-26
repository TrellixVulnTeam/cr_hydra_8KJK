#!/usr/bin/env python
"""
check the database for inversions
"""
import logging
import os
import hashlib
import io
import tarfile
import json

from sqlalchemy import create_engine
import IPython

from cr_hydra.settings import get_config

IPython

logging.basicConfig(
    level=logging.INFO,
    format='{asctime} - {name} - %{levelname} - {message}',
    style='{',
)
logger = logging.getLogger(__name__)

global_settings = get_config()

engine = create_engine(
    global_settings['general']['db_credentials'],
    echo=False, pool_size=10, pool_recycle=60,
)


def _is_finished(sim_id, conn):
    """Check if the simulation has been processed.

    Ignore any rows already locked by other processes (i.e., concurrent runs
    of crh_retrieve)

    Returns None if the given inversion is not finished or unavailable

    """
    result = conn.execute(
        ' '.join((
            'select tomodir_finished_file from inversions',
            'where index=%(sim_id)s and status=\'finished\'',
            'and downloaded=\'f\'',
            'for update',
            'skip locked',
            ';'
        )),
        sim_id=sim_id
    )
    if result.rowcount == 1:
        return result.fetchone()[0]
    else:
        result.close()
        return None


def _check_and_retrieve(filename):
    """For a given .crh file, check if the inversion results are ready to be
    downloaded and extract the results

    Returns
    -------

    """
    status = False
    logger.info('Checking: {}'.format(filename))
    sim_settings = json.load(open(filename, 'r'))
    # ignore any simulation not successfully uploade
    if 'sim_id' not in sim_settings:
        return False

    conn = engine.connect()
    transaction = conn.begin_nested()

    final_data_id = _is_finished(sim_settings['sim_id'], conn)

    tomodir_name = os.path.basename(filename)[:-4]
    basedir = os.path.abspath(os.path.dirname(filename))

    pwd = os.getcwd()

    if final_data_id is not None:
        # we got data
        result = conn.execute(
            'select hash, data from binary_data where index=%(data_id)s;',
            data_id=final_data_id
        )
        assert result.rowcount == 1
        file_hash, binary_data = result.fetchone()

        # check hash
        m = hashlib.sha256()
        m.update(binary_data)
        assert file_hash == m.hexdigest()

        logger.info('retrieving and unpacking')
        os.chdir(basedir)

        # unpack
        fid = io.BytesIO(bytes(binary_data))
        with tarfile.open(fileobj=fid, mode='r') as tar:
            assert os.path.abspath(os.getcwd()) == os.path.abspath(basedir)

            # make sure there are only files in the archive that go into the
            # tomodir
            for entry in tar.getnames():
                if entry == '.':
                    continue
                # strip leading './'
                if entry.startswith('./'):
                    entry = entry[2:]
                if not entry.startswith(tomodir_name):
                    raise Exception('Content should go into tomodir')
            # now extract
            def is_within_directory(directory, target):
                
                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)
            
                prefix = os.path.commonprefix([abs_directory, abs_target])
                
                return prefix == abs_directory
            
            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
            
                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")
            
                tar.extractall(path, members, numeric_owner=numeric_owner) 
                
            
            safe_extract(tar, ".")
        os.chdir(pwd)
        mark_sim_as_downloaded(sim_settings['sim_id'], conn)
        status = True
        os.unlink(filename)
        # IPython.embed()
    transaction.commit()
    conn.close()
    engine.dispose()
    return status


def mark_sim_as_downloaded(sim_id, conn):
    # mark the simulation as downloaded and delete the files
    result = conn.execute(
        'select tomodir_unfinished_file, tomodir_finished_file from ' +
        'inversions where index=%(sim_id)s;',
        sim_id=sim_id
    )
    assert result.rowcount == 1
    file_ids = list(result.fetchone())
    result = conn.execute(
        'update inversions set ' +
        'tomodir_unfinished_file=NULL, ' +
        'tomodir_finished_file=NULL, ' +
        'downloaded=\'t\' where index=%(sim_id)s;',
        sim_id=sim_id
    )
    assert result.rowcount == 1
    result.close()
    # delete
    result = conn.execute(
        'delete from binary_data where index in (%(id1)s, %(id2)s);',
        id1=file_ids[0],
        id2=file_ids[1],
    )
    result.close()


def retrieve_all_finished_mods_and_invs():
    unfinished = False
    for root, dirs, files in os.walk('.'):
        dirs.sort()
        files.sort()
        for filename in files:
            if filename.endswith('.crh'):
                status = _check_and_retrieve(root + os.sep + filename)
                if not status:
                    unfinished = True
    return unfinished


def main():
    retrieve_all_finished_mods_and_invs()


if __name__ == '__main__':
    main()
