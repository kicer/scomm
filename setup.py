from distutils.core import setup
import py2exe

excludes = ['_gtkagg', '_tkagg', 'bsddb', 'curses', 'email', 'pywin.debugger', 'pywin.debugger.dbgcon', 'pywin.dialogs']

setup(
	options = {"py2exe":
		{
			"excludes": excludes,
		}
	},
	windows = [{ 'script':'scomm.py', 'icon_resources':[(1, 'logo.ico')]}],
	zipfile = None,
	data_files = [('', ['usercfg.ini','app.ui','unpack.ui','data.ui','logo.ico'])]
)
