from distutils.core import setup
import py2exe

excludes = ['_gtkagg', '_tkagg', 'bsddb', 'curses', 'email', 'pywin.debugger', 'pywin.debugger.dbgcon', 'pywin.dialogs']

setup(
	options = {"py2exe":
		{
			"excludes": excludes,
            "bundle_files": 1,
            "compressed": True,
            "optimize": 2,
		}
	},
	windows = [{ 'script':'scomm.py', 'icon_resources':[(1, 'app.ico')]}],
	zipfile = None,
	data_files = [('', ['usercfg.json','app.ui','unpack.ui','data.ui','README.md'])]
)
