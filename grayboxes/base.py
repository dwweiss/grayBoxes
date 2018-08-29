"""
  Copyright (c) 2016- by Dietmar W Weiss

  This is free software; you can redistribute it and/or modify it
  under the terms of the GNU Lesser General Public License as
  published by the Free Software Foundation; either version 3.0 of
  the License, or (at your option) any later version.

  This software is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
  Lesser General Public License for more details.

  You should have received a copy of the GNU Lesser General Public
  License along with this software; if not, write to the Free
  Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
  02110-1301 USA, or see the FSF site: http://www.fsf.org.

  Version:
      2018-08-28 DWW

  Note on program arguments:
    - no arguments          : program starts in default mode
    - two arguments: 'path inputFile'
                            : command line mode with password protection
    - three arguments '-s path inputFile'
                            : command line mode, no password
    - two arguments '-s -g' : graphic mode, no console output
    - one argument '-g'     : graphic mode with information to console

"""

import os
import sys
from datetime import datetime
from getpass import getpass
from hashlib import sha224
from re import sub
from time import time
from tempfile import gettempdir
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union
import numpy as np
try:
    from tkinter import Button
    from tkinter import Entry
    from tkinter import Label
    from tkinter import messagebox
    from tkinter import Tk
except ImportError:
    print("\n!!! Wrong Python interpreter (version: '" +
          str(sys.version_info.major) + '.' + str(sys.version_info.major) +
          '.' + str(sys.version_info.micro) + "') or 'tkinter' not imported")
import logging
logger = logging.getLogger(__name__)

try:
    import grayboxes.parallel as parallel
except ImportError:
    try:
        import parallel as parallel
    except ImportError:
        print("!!! Module 'parallel' not imported")


class Base(object):
    """
    Connects model objects and controls their execution

    The objects are organized in overlapping tree structures. The 
    concept of conservative leader-follower relationships 
    (authoritarian) is extended by leader-cooperator relationships 
    (partnership). The differentiation into leader-follower and 
    leader-cooperator relationships allows the creation of complex 
    object structures which can coexist in space, time or abstract 
    contexts.

    The implementation supports:

    - Distributed development of objects derived from the connecting 
      Base class

    - Object specialization in "vertical" and "horizontal" direction
        - leader-type objects implementing alternative control of tasks
        - peer-type opjects implement empirical submodels (data-driven),
          theoretical submodels, knowledge objects (e.g. properties of 
          matter) and generic service objects (e.g. plotting)

     - Uniform interface to code execution of objects derived from the
       connector class objects via public methods
        - pre-process:   pre() which calls load()
        - main task:    task() which is called by control()
        - post-process: post() which calls save()

      The __call__() method calls pre(), control() and post() 
      recursively. Iterative or transient repetition of the task() 
      method will be controlled in derived classes by a overloaded 
      control(), see class Loop


    leader object
       ^
       |
     --|---------                                transient or
    | leader()   |                            ---iterative----
    |------------|        ---> pre()         |                ^
    |            |       |                   v                |
    | self.__call__() ---+---> control() ----o---> task() ----o---> stop
    |            |       |
    |            |        ---> post()
    |            |
    |------------|
    | follower() |
    --|---------
      |-> follower/cooperator.__call__()
      |-> follower/cooperator.__call__()
      :

      The execution sequence in a tree of objects is outlined in the 
      figure below: recursive call of pre() for object (1) and its 
      followers (11), (12), (111), (112) and its cooperators (21) and 
      (211).

      Execution of methods task() and post() is similar. Note that 
      method pre() of object (2) is not executed.

       -----------                                   -----------
      | no leader |                                 | no leader |
      |-----------|                                 |-----------|
      |           |                                 |           |
      |object (1) |                                 |object (2) |
      |   Base -----> pre()                         |    Base   |
      |           |                                 |           |
      |-----------|                                 |-----------|
      | follower()|                                 | follower()|
       --|--------                                   --|----------
         |                                             |
         +----------------------+---------------+      |
         |                      |               |      |
       --|--------            --|--------       |    --|--------
      | leader()  |          | leader()  |      |   | leader()  |
      |-----------|          |-----------|      |   |-----------|
      |           |          |           |      +-->|           |
      |object (11)|          |object (12)|          |object (21)|
      |   Base -----> pre()  |   Base -----> pre()  |   Base ----> pre()
      |           |          |           |          |           |
      |-----------|          |-----------|          |-----------|
      | follower()|          |no follower|          | follower()|
       --|--------            -----------            --|--------
         |                                             |
         +----------------------+                      |
         |                      |                      |
       --|--------            --|--------            --|--------
      | leader()  |          | leader()  |          | leader()  |
      |-----------|          |-----------|          |-----------|
      |           |          |           |          |           |
      |object(111)|          |object(112)|          |object(211)|
      |   Base -----> pre()  |   Base -----> pre()  |   Base ----> pre()
      |           |          |           |          |           |
      |-----------|          |-----------|          |-----------|
      |no follower|          |no follower|          |no follower|
       -----------            -----------           ------------
    """

    def __init__(self, identifier: str='Base', argv: List[str]=None) -> None:
        """
        Initializes object

        Args:
            identifier (string, optional):
                unique identifier of object

                argv (positional arguments, optional):
                    program arguments
        """
        if not identifier:
            identifier = self.__class__.__name__
        self._identifier = str(identifier)
        self.argv = argv
        self.program = self.__class__.__name__
        self.version = '280818_dww'

        self._execTimeStart = 0.0       # start measure execution time
        self._minExecTimeShown = 1.0    # times < limit are not shown
        self.path = None                # path to files,see @path.setter
        self.extension = None           # file ext,see @extension.setter

        self._gui = False               # no graphic interface if False
        self._batch = False             # no user interaction if True
        self._silent = False            # no console output if True

        self._ready = True              # if True, successful train/pred

        self._preDone = False           # internal: True if  pre() done
        self._taskDone = False          # internal: True if task() done
        self._postDone = False          # internal: True if post() done


        self._leader = None             # leader object
        self._followers = []            # array of follower objects

        self._data = None               # data organized in a DataFrame
        self._csvSeparator = ','        # separator in csv-files
        
    def __call__(self, **kwargs: Dict[str, Any]) -> float:
        """
        Executes model

        Args:
            kwargs (dict, optional):
                keyword arguments passed to pre(), control() and post()

                silent (bool):
                    if True then suppress printing
        Returns:
            (float):
                residuum from range 0.0 .. 1.0 indicating error of task
                or -1.0 if parallel and rank > 0
        """
        # skip model execution if parallelized with MPI and rank > 0
        if 'parallel' in sys.modules and parallel.rank():
            return -1.0

        self.silent = kwargs.get('silent', self.silent)

        self.prolog()
        self.pre(**kwargs)

        res = self.control(**kwargs)
        self.post(**kwargs)
        self.epilog()

        return res

    def __str__(self) -> str:
        s = ''
        if not self.leader:
            s += "@root: '" + self.identifier + "', \n"
        s += "{identifier: '" + self.identifier + "'"
        if self.leader:
            s += ", level: '" + str(self.treeLevel()) + "'"
            s += ", leader: '" + self.leader.identifier + "'"
            if self.identifier != self.leader:
                s += ' (follower)'
        if self.followers:
            s += ", followers: ["
            for x in self.followers:
                if x:
                    s += "'" + x.identifier + "', "
                else:
                    s += "'None', "
            if self.followers:
                s = s[:-2]
            s += ']'
        s += '}'

        for x in self.followers:
            if x:
                s += ',\n' + x.indent() + str(x)
                # if self.isCooperator(x): s = '# (cooperator)'
        return s

    def destruct(self) -> bool:
        """
        Destructs all followers. Cooperators will be kept
        
        Returns:
            (bool):
                True on success
        """
        if self._data:
            del self._data
        if self.isRoot():
            logging.shutdown()

        return self.destructDownwards(fromNode=self)

    def destructDownwards(self, fromNode: 'Base') -> bool:
        """
        Destructs all followers downwards from 'fromNode'. Cooperators 
        will be kept
        
        Returns:
            (bool):
                True on success
        """
        if not fromNode:
            return False
        for i in range(len(fromNode.followers)):
            node = fromNode.followers[i]
            if node:
                if id(node.leader) == id(fromNode):
                    self.destructDownwards(node)
        if fromNode.leader:
            fromNode.leader._destructFollower(fromNode)
        return True

    def _destructFollower(self, node: 'Base') -> bool:
        """
        Destructs the followers of 'node'. Cooperators will be kept
        
        Args:
            node (Base):
                actual node
                
        Returns:
            (bool): False if this node has no followers
        """
        if not node:
            return False
        i = -1
        for index, val in enumerate(self.followers):
            if id(val) == id(node):
                i = index
                break
        if i == -1:
            return False
        if self.isCooperator(node):
            return False
        del node._data
        self._followers[i] = None
        return True

    def root(self) -> 'Base':
        """
        Returns:
            (Base):
                root node of this tree (the leader of root is None)
        """
        p = self
        while p.leader:
            p = p.leader
        return p

    def treeLevel(self) -> int:
        """
        Returns:
            (int):
                level of this node in tree, relative to root (root is 0)
        """
        n = 0
        p = self.leader
        while p:
            p = p.leader
            n += 1
        return n

    def indent(self) -> str:
        return (4 * ' ') * self.treeLevel()

    @property
    def identifier(self) -> str:
        return self._identifier

    @identifier.setter
    def identifier(self, value: str):
        if value:
            self._identifier = str(value)
        else:
            self._identifier = self.__class__.__name__

    @property
    def argv(self) -> List[str]:
        return self._argv

    @argv.setter
    def argv(self, value: Optional[List[str]]):
        if value is None:
            self._argv = sys.argv
        else:
            self._argv = value

    @property
    def gui(self) -> bool:
        return self._gui

    @gui.setter
    def gui(self, value: bool):
        if 'tkinter' not in sys.modules:
            value = False
            self.warn("!!! 'gui' is not set: no module 'tkinter'")
        self._gui = value
        for x in self._followers:
            x._gui = value

    @property
    def batch(self) -> bool:
        return self._batch

    @batch.setter
    def batch(self, value: bool):
        self._batch = value
        for x in self._followers:
            x._batch = value

    @property
    def silent(self) -> bool:
        return self._silent or ('parallel' in sys.modules and parallel.rank())

    @silent.setter
    def silent(self, value: bool):
        self._silent = value

    @property
    def ready(self) -> bool:
        return self._ready

    @ready.setter
    def ready(self, value: bool):
        self._ready = value

    @property
    def path(self) -> str:
        return self._path

    @path.setter
    def path(self, value: Union[str, Path]):
        if not value:
            self._path = gettempdir()
        else:
            self._path = Path(str(value))

    @property
    def extension(self) -> str:
        return str(self._extension)

    @extension.setter
    def extension(self, value: str):
        if not value:
            self._extension = ''
        else:
            if not value.startswith('.'):
                self._extension = '.' + str(value)
            else:
                self._extension = str(value)

    @property
    def csvSeparator(self) -> str:
        return str(self._csvSeparator)

    @csvSeparator.setter
    def csvSeparator(self, value: str):
        if value is None:
            self._csvSeparator = ' '
        else:
            self._csvSeparator = value

    @property
    def leader(self) -> 'Base':
        return self._leader

    @leader.setter
    def leader(self, other: 'Base'):
        if other:
            other.setFollower(self)

    @property
    def followers(self) -> List['Base']:
        return self._followers

    @followers.setter
    def followers(self, other: Iterable['Base']) -> None:
        self.terminate("followers.setter: 'followers' is protected," +
                       " use 'setFollower()'")

    def isRoot(self) -> bool:
        return not self.leader

    @property
    def data(self) -> Any:
        return self._data

    @data.setter
    def data(self, other: Any):
        if self._data is not None:
            if not self.silent:
                print("+++ data.setter: delete 'data'")
            del self._data
        self._data = other

    def __getitem__(self, identifier: str) -> Optional['Base']:
        """
        Indexing, eg b = Base(); b.setFollower(['f1','f2']); f = b['f1']

        Searches for node with 'identifier'. Starts downwards from root.

        Args:
            identifier (str):
                identifier of searched node

        Returns:
            (Base):
                node with given identifier or None if node not found
        """
        return self.getFollower(identifier)

    def getFollower(self, identifier: str) -> Optional['Base']:
        """
        Search for node with 'identifier'. Search starts downwards 
        from root

        Args:
            identifier (str):
                identifier of searched node

        Returns:
            (Base):
                node with given identifier or None if node not found
        """
        return self.getFollowerDownwards(identifier, fromNode=None)

    def getFollowerDownwards(self, identifier: str, fromNode: 
        Optional['Base']=None) -> Optional['Base']:
        """
        Search for node with given 'identifier', start search downwards
        from 'fromNode'

        Args:
            identifier (str):
                identifier of wanted node

            fromNode (Base or None, optional):
                start node for downward search. If 'fromNode' is None, 
                search starts from root

        Returns:
            (Base)
                node with given identifier or None if node not found
        """
        if self.identifier == identifier:
            return self
        if fromNode:
            if fromNode._identifier == identifier:
                return fromNode
        else:
            fromNode = self.root()
            if not fromNode:
                return None
        if fromNode.identifier == identifier:
            return fromNode
        for i in range(len(fromNode.followers)):
            node = fromNode.followers[i]
            if node:
                node = self.getFollowerDownwards(identifier, node)
                if node:
                    return node
        return None

    def setFollower(self, other: Union['Base', Iterable['Base']]) -> 'Base':
        """
        Adds other node

        Args:
            other (Base or iterable of Base):
                other node(s)

        Returns:
            (Base):
                other node
        """
        if other:
            if not isinstance(other, (list, tuple)):
                other._leader = self
                if other not in self._followers:
                    self._followers.append(other)

            else:
                for obj in other:
                    obj._leader = self
                    if obj not in self._followers:
                        self._followers.append(obj)
        return other

    def isFollower(self, other: 'Base') -> bool:
        """
        Returns:
            (bool):
                True if 'other' is a follower of this node 
        """
        return other._leader == self and other in self._followers

    def setCooperator(self, other: Union['Base', Iterable['Base']]) -> 'Base':
        if other:
            if not isinstance(other, (list, tuple)):
                if other not in self._followers:
                    self._followers.append(other)
            else:
                for obj in other:
                    if obj not in self._followers:
                        self._followers.append(obj)
        return other

    def isCooperator(self, other: 'Base') -> bool:
        """
        Returns:
            (bool):
                True if 'other' is a cooperator of this node 
        """
        return other._leader != self and other in self._followers

    def cleanString(self, s: str) -> str:
        return sub('[ \t\n\v\f\r]', '', s)

    def reverseString(self, s: str) -> str:
        rs = list(s)
        rs.reverse()
        return ''.join(rs)

    def kwargsDel(self, kwargs: Dict[str, Any], 
                  remove: Union[str, List[str]]) -> Dict[str, Any]:
        """
        Makes copy of keyword dictionary and removes given key(s)

        Args:
            kwargs (dict):
                keyword arguments

            remove (str or list of str):
                keywords of items to be removed

        Returns:
            dict of keyword arguments without removed items
        """
        dic = kwargs.copy()
        for key in np.atleast_1d(remove):
            if key in dic:
                del dic[key]
        return dic

    def kwargsGet(self, kwargs: Dict[str, Any], 
                  keys: Union[str, List[str]], default: Any=None) -> Any:
        """
        Returns value of kwargs for first matching key or 'default' if 
        all keys are invalid

        Args:
            kwargs (dict):
                keyword arguments

            keys (str or list of str):
                keyword or list of alternative keywords

            default(Any, optional):
                value to be returned if none of the keys is in kwargs

        Returns:
            (Any):
                value of first matching key or 'default'
        """
        for key in np.atleast_1d(keys):
            if key in kwargs:
                return kwargs[key]
        return default

    def terminate(self, message: str='') -> None:
        if not message:
            message = 'Fatal error'

        if not self.silent:
            print("\n???\n??? '" + self.program + "', terminated due to: '" +
                  message + "'\n???")
        if self.gui:
            messagebox.showerror("Termination: '" + self.program + "'",
                                 message)
        logger.critical(self.identifier + ' : ' + message)
        self.destruct()
            
        sys.exit()

    def warn(self, message: str='', wait: bool=False) -> None:
        """
        - Sends message to logger
        - Sends message to TKinter widget if in GUI mode, otherwise to console

        Args:
            message (str):
                warning to be written to log file and console
        """
        if not self.silent:
            print("!!! '" + self.program  + "', warning: '" +  message + "'")
        if self.gui:
            messagebox.showinfo(self.program + ' - Warning', message)
        logger.warning(self.identifier + ' : ' + message)
        if not self.silent and wait:
            # consider to replace input() with os.system('pause')
            input('!!! Press Enter to continue ...')

    def write(self, message: str) -> None:
        """
        - Sends message to logger with file handler
        - Sends message to console if not in silent mode

        Args:
            message (str):
                message to be written to log file and console
        """
        now = datetime.now().strftime('%H:%M:%S.%f')[:-4]
        if not self.silent:
            print(self.indent() + message)
        logger.info(now + ' ' + self.indent() + message)

    def _authenticate(self) -> None:
        """
        Asks for password. Terminates program if wrong password

        Note:
            Create new hash string 's' with:
                import hashlib
                s = hashlib.sha224(
                    'new password'.encode('UTF-8')).hexdigest()
        """
        s = 'c0dad715ce5501ea5e382d3a44a7cf816f9a1a309dfeb88cbe9ebfbd'
        if self.gui:
            parent = Tk()
            parent.title(self.program)
            Label(parent, text='').grid(row=0, column=0)
            Label(parent, text='Enter password').grid(row=1, column=0)
            Label(parent, text='').grid(row=2, column=0)
            entry2 = Entry(parent, show='*')
            entry2.grid(row=1, column=1)
            Button(parent, text='Continue',
                   command=parent.quit).grid(row=3, column=5, pady=10)
            parent.mainloop()
            pw = entry2.get()
            parent.withdraw()
        else:
            sys.stdout.flush()
            pw = getpass('Enter password: ')
        if sha224(pw.encode('UTF-8')).hexdigest() != s:
            self.terminate('wrong password')

    def prolog(self, purpose: str='Processing data',
               usage: str='[ path sourceFile [ -s -g ] ]',
               example: str='-g -s /tmp test.xml') -> None:
        if '-h' in self.argv or '--help' in self.argv:
            print("This is: '" + self.program + "', version " + self.version)
            print('\nPurpose: ' + purpose)
            print('Usage:   ' + self.program + ' ' + usage)
            print('Example: ' + self.program + ' ' + example)
            exit()

        authenticate = False
        if len(self.argv) > 1+0:
            self.gui = '-g' in self.argv or '--gui' in self.argv
            self.silent = '-s' in self.argv or '--silent' in self.argv
            if not self.gui and self._silent:
                authenticate = False
        else:
            if not self.gui:
                # self.silent = False
                pass

        global logger
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            f = os.path.join(os.path.join(self.path, self.identifier + '.log'))
            handler = logging.FileHandler(f, mode='w')
            handler.setLevel(logging.DEBUG)
            logger.addHandler(handler)
 
        if self.isRoot():
            if authenticate:
                self._authenticate()                
                
            message = "*** This is: '" + self.program + "'"
            if self.identifier and self.identifier != self.program:
                message += ", id: '" + self.identifier + "'"
            message += ", version: '" + self.version + "'"            
            self.write(message)            
            self.write('    Date: ' + str(datetime.now().date()) +
                       ' ' + str(datetime.now().time())[:8])
            self.write('    Path: ' + "'" + str(self.path) + "'")
            self.write('=== Pre-processing')
            self._execTimeStart = time()

    def epilog(self) -> None:
        if self.isRoot():
            message = "'" + self.program + "' is successfully completed\n"
            execTime = time() - self._execTimeStart
            if execTime >= self._minExecTimeShown:
                self.write('    Execution time: ' + format(round(execTime, 2)))
            self.write('*** ' + message)

        for x in self.followers:
            x.epilog()

            if self.gui:
                messagebox.showinfo(self.program, message)

        if logger.handlers:
            logger.info('')
            logger.handlers = []
        sys.stdout.flush()

    def load(self) -> bool:
        return True

    def save(self) -> bool:
        return True

    def initialCondition(self) -> bool:
        # super().initialCondition()         # use it in derived classes
        pass

    def updateNonLinear(self) -> bool:
        # super().updateNonLinear()          # use it in derived classes
        pass

    def updateTransient(self) -> bool:
        # super().updateTransient()          # use it in derived classes
        pass

    def pre(self, **kwargs: Dict[str, Any]) -> bool:
        """
        Args:
            kwargs (dict, optional):
                keyword arguments

        Returns:
            (bool):
                False if data loading failed
        """
        ok = True
        for x in self.followers:
            x.pre(**kwargs)
            if self.isCooperator(x):
                self.write(self.indent() + "    ['" + x.identifier +
                           "' is cooperator]")
        if self.root().followers:
            self.write('--- Pre (' + self.identifier + ')')

        if self.data is None:
            ok = self.load()
        self._preDone = True
        sys.stdout.flush()
        return ok

    def task(self, **kwargs: Dict[str, Any]) -> float:
        """
        Args:
            kwargs (dict, optional):
                keyword arguments

        Returns:
            (float):
                residuum from range [0., 1.], indicating error
        """
        for x in self.followers:
            x.task(**kwargs)
            if self.isCooperator(x):
                self.write(self.indent() + "    ['" + x.identifier +
                           "' is cooperator]")
        if self.root().followers:
            self.write('--- Task (' + self.identifier + ')')
        self._taskDone = True
        sys.stdout.flush()
        return 0.0

    def post(self, **kwargs: Dict[str, Any]) -> bool:
        """
        Args:
            kwargs (dict, optional):
                keyword arguments

        Returns:
            (bool):
                if False, data saving failed
        """
        ok = True
        for x in self.followers:
            x.post(**kwargs)
            if self.isCooperator(x):
                self.write(self.indent() + "    ['" + x.identifier +
                           "' is cooperator]")
        if self.root().followers:
            self.write('--- Post (' + self.identifier + ')')
        if self.data is None:
            ok = self.save()
        self._postDone = True
        sys.stdout.flush()
        return ok

    def control(self, **kwargs: Dict[str, Any]) -> float:
        """
        Args:
            kwargs (dict, optional):
                keyword arguments passed to task()

        Returns:
            (float):
                residuum from range [0., 1.], indicating error of task
        """
        if self.isRoot():
            execTime = time() - self._execTimeStart
            if execTime >= self._minExecTimeShown:
                self.write('    Execution time: {:2f} s'.format(round(execTime,
                                                                      2)))
            self._execTimeStart = time()

        if self.isRoot():
            self.write('=== Task-processing')
        res = self.task(**kwargs)

        if self.isRoot():
            execTime = time() - self._execTimeStart
            if execTime >= self._minExecTimeShown:
                self.write('    Execution time: {:2f} s'.format(round(execTime,
                                                                      2)))
            self._execTimeStart = time()
        self.write('=== Post-processing')
        return res
