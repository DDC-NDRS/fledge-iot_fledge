/*
 * FogLAMP plugin handle related
 *
 * Copyright (c) 2018 OSisoft, LLC
 *
 * Released under the Apache 2.0 Licence
 *
 * Author: Amandeep Singh Arora
 */

#include <iostream>
#include <unordered_map>
#include <logger.h>
#include <config_category.h>
#include <reading.h>
#include <logger.h>
#include <utils.h>
#include <plugin_handle.h>

//#include <Python.h>

#define PRINT_FUNC	Logger::getLogger()->info("%s:%d", __FUNCTION__, __LINE__);

PLUGIN_INFORMATION *Py2C_PluginInfo(PyObject* pyRetVal);
static void logErrorMessage();
PLUGIN_INFORMATION *plugin_info_fn();

using namespace std;

#if 0
	// Setup the function pointers to the plugin
  	pluginStartPtr = (void (*)(PLUGIN_HANDLE))
				manager->resolveSymbol(handle, "plugin_start");
  	pluginPollPtr = (Reading (*)(PLUGIN_HANDLE))
				manager->resolveSymbol(handle, "plugin_poll");
  	pluginReconfigurePtr = (void (*)(PLUGIN_HANDLE, const std::string&))
				manager->resolveSymbol(handle, "plugin_reconfigure");
  	pluginShutdownPtr = (void (*)(PLUGIN_HANDLE))
				manager->resolveSymbol(handle, "plugin_shutdown");
	if (isAsync())
	{
  		pluginRegisterPtr = (void (*)(PLUGIN_HANDLE, INGEST_CB cb, void *data))
				manager->resolveSymbol(handle, "plugin_register_ingest");
	}

	pluginShutdownDataPtr = (string (*)(const PLUGIN_HANDLE))
				 manager->resolveSymbol(handle, "plugin_shutdown");
	pluginStartDataPtr = (void (*)(const PLUGIN_HANDLE, const string& storedData))
			      manager->resolveSymbol(handle, "plugin_start");
#endif


typedef enum {
	PLUGIN_INIT,
	PLUGIN_START,
	PLUGIN_POLL,
	PLUGIN_RECONF,
	PLUGIN_SHUTDOWN,
	PLUGIN_REGISTER
} PluginFuncType;

std::unordered_map<std::string, PluginFuncType> pluginFuncTypeMap = {
															{"plugin_init", PLUGIN_INIT}, 
															{"plugin_start", PLUGIN_START}, 
															{"plugin_poll", PLUGIN_POLL}, 
															{"plugin_reconfigure", PLUGIN_RECONF}, 
															{"plugin_shutdown", PLUGIN_SHUTDOWN}, 
															{"plugin_register_ingest", PLUGIN_REGISTER}
														  };

#if 0
	void		(*pluginStartPtr)(PLUGIN_HANDLE);
	Reading		(*pluginPollPtr)(PLUGIN_HANDLE);
	void		(*pluginReconfigurePtr)(PLUGIN_HANDLE,
					        const std::string& newConfig);
	void		(*pluginShutdownPtr)(PLUGIN_HANDLE);
	void		(*pluginRegisterPtr)(PLUGIN_HANDLE, INGEST_CB, void *);
#endif

#if 0
void* BinaryPluginHandle::CallPluginFunc(const char *func, va_list argList)
{
	if (pluginFuncTypeMap.find(func) == pluginFuncTypeMap.end())
	{
		logger->info("%s:%d: returning NULL", __FUNCTION__, __LINE__);
		return NULL;
	}

	void		(*pluginStartPtr)(PLUGIN_HANDLE);
	Reading		(*pluginPollPtr)(PLUGIN_HANDLE);
	void		(*pluginReconfigurePtr)(PLUGIN_HANDLE,
					        const std::string& newConfig);
	void		(*pluginShutdownPtr)(PLUGIN_HANDLE);
	void		(*pluginRegisterPtr)(PLUGIN_HANDLE, INGEST_CB, void *);

	switch(pluginFuncTypeMap.find(func)->second)
	{
		case PLUGIN_INIT:
			{
			pluginInitPtr = (PLUGIN_HANDLE (*)(const void *))
										ResolveSymbol("plugin_init");
			ConfigCategory *config = va_arg(argList, ConfigCategory*);
			void *rv = (*pluginInitPtr)(handle, config);
			return rv;
			}
			break;

		case PLUGIN_START:
			{
			pluginStartPtr = (void (*)(PLUGIN_HANDLE))
										ResolveSymbol("plugin_start");
			void *rv = (*pluginStartPtr)(handle);
			return;
			}
			break;

			
		case PLUGIN_POLL:
			{
			pluginPollPtr = (Reading (*)(PLUGIN_HANDLE))
										ResolveSymbol(handle, "plugin_poll");
			Reading rdng = (*pluginPollPtr)(handle);
			return ((void*) rdng);
			}
			break;
	}
	
	
}
#endif

PyObject* pModule;

PythonPluginHandle::PythonPluginHandle(const char *name, const char *_path)
{
	// Python 3.5 loaded filter module handle
	// pModule = NULL;

	string path(_path);
	
	// Python 3.5  script name
	std::size_t found = path.find_last_of("/");
	string pythonScript = path.substr(found + 1);
	string filtersPath = path.substr(0, found);
	//filtersPath = path.substr(0, filtersPath.find_last_of("/"));
	
	// Embedded Python 3.5 program name
	wchar_t *programName = Py_DecodeLocale(name, NULL);
    Py_SetProgramName(programName);
	PyMem_RawFree(programName);

	const char* foglampRootDir = getenv("FOGLAMP_ROOT");
	string foglampPythonDir = (string(foglampRootDir) + "/python");
	
	// Embedded Python 3.5 initialisation
    Py_Initialize();

	// Get FogLAMP Data dir
	//string filtersPath = getDataDir() + PYTHON_FILTERS_PATH;
	Logger::getLogger()->info("%s:%d: filtersPath=%s, pythonScript=%s", __FUNCTION__, __LINE__, filtersPath.c_str(), pythonScript.c_str());
	
	// Set Python path for embedded Python 3.5
	// Get current sys.path. borrowed reference
	PyObject* sysPath = PySys_GetObject((char *)"path");
	// Add FogLAMP python filters path
	PyList_Append(sysPath, PyUnicode_FromString((char *) filtersPath.c_str()));
	PyList_Append(sysPath, PyUnicode_FromString((char *) foglampPythonDir.c_str()));
	//PyObject* pPath = PyUnicode_DecodeFSDefault((char *)filtersPath.c_str());
	//PyList_Insert(sysPath, 0, pPath);
	// Remove temp object
	//Py_CLEAR(pPath);

	//sysPath = PySys_GetObject((char *)string("path").c_str());
	//Logger::getLogger()->info("%s:%d: sysPath=%s", __FUNCTION__, __LINE__, PyBytes_AsString(sysPath));
	//Py_CLEAR(sysPath);

	// 2) Import Python script
	pModule = PyImport_ImportModule(name);

	// Check whether the Python module has been imported
	if (!pModule)
	{
		// Failure
		if (PyErr_Occurred())
		{
			logErrorMessage();
		}
		Logger::getLogger()->fatal("PythonPluginHandle c'tor: cannot import Python 3.5 script "
					   "'%s' from '%s' : pythonScript=%s, filtersPath=%s",
					   name, _path,
					   pythonScript.c_str(),
					   filtersPath.c_str());
	}
	Logger::getLogger()->info("%s:%d: python module loaded successfully, pModule=%p", __FUNCTION__, __LINE__, pModule);

#if 1
 	PyObject* pFunc;
	pFunc = PyObject_GetAttrString(pModule, "plugin_info");
	if (!pFunc)
    {
		PRINT_FUNC;
        PyErr_Print();
    }
	PRINT_FUNC;
	Logger::getLogger()->info("c'tor: pFunc=%p", pFunc);

	if (!pFunc || !PyCallable_Check(pFunc))
	{
		PRINT_FUNC;
		// Failure
		if (PyErr_Occurred())
		{
			logErrorMessage();
		}
		PRINT_FUNC;

		Logger::getLogger()->fatal("Cannot find method plugin_info in loaded python module");
		Py_CLEAR(pFunc);

		return;
	}
	
	PRINT_FUNC;
	
	// - 2 - Call Python method passing an object
	PyObject* pReturn = PyObject_CallFunction(pFunc, NULL);

	PRINT_FUNC;

	PLUGIN_INFORMATION *info = NULL;

	// - 3 - Handle filter returned data
	if (!pReturn)
	{
		// Errors while getting result object
		Logger::getLogger()->error("Called python script method plugin_info : error while getting result object");

		// Errors while getting result object
		logErrorMessage();

		// Filter did nothing: just pass input data
		info = NULL;
	}
	else
	{
		PRINT_FUNC;
		
		// Get new set of readings from Python filter
		info = Py2C_PluginInfo(pReturn);
		
		// Remove pReturn object
		Py_CLEAR(pReturn);
	}
	if(info)
		Logger::getLogger()->info("plugin_handle: plugin_info(): info={name=%s, version=%s, options=%d, type=%s, interface=%s, config=%s}", 
					info->name, info->version, info->options, info->type, info->interface, info->config);

#else
	PyObject* dict = PyModule_GetDict(pModule);
	PyObject *pstr = PyRun_String("message", Py_eval_input, dict, dict);

	char *cstr;
	PyArg_Parse(pstr, "s", &cstr);
	Logger::getLogger()->info("dict=%s", cstr);

/*
	if (!PyDict_Check(dict)) throw error;
	PyObject *key;
	PyObject *value;
	Py_ssize_t pos = 0;

	while (PyDict_Next(dict, &pos, &key, &value))
	{
		Logger::getLogger()->info("dict elem: {%s, %s}", PyDict_GetItemString(key), PyDict_GetItemString(value));
	}

	(void) plugin_info_fn();
*/
#endif
}

#if 0
void* PythonPluginHandle::openHandle(const char *)
{
	return NULL;
}
#endif

PythonPluginHandle::~PythonPluginHandle()
{
	// Decrement pModule reference count
	Py_CLEAR(pModule);
	// Decrement pFunc reference count
	// Py_CLEAR(info->pFunc);

	// Cleanup Python 3.5
	Py_Finalize();
}

void *PythonPluginHandle::ResolveSymbol(const char *sym)
{
	if (sym == "plugin_info")
		return (void *) plugin_info_fn;
	else
	{
		Logger::getLogger()->info("PythonPluginHandle::ResolveSymbol returnung NULL for sym=%s", sym);
		return NULL;
	}
#if 0
	else if (sym == "plugin_init")
		return (void *) plugin_init;
	else if (sym == "plugin_start")
		return (void *) plugin_start;
	else if (sym == "plugin_poll")
		return (void *) plugin_poll;
	else if (sym == "plugin_reconfigure")
		return (void *) plugin_reconfigure;
	else if (sym == "plugin_shutdown")
		return (void *) plugin_shutdown;
	else if (sym == "plugin_register_ingest")
		return (void *) plugin_register_ingest;
#endif
}

void *PythonPluginHandle::GetInfo()
{
	Logger::getLogger()->info("PythonPluginHandle::GetInfo()");
	return (void *) plugin_info_fn;
}
	
PLUGIN_INFORMATION *plugin_info_fn()
{
	PyObject* pFunc;
	Logger::getLogger()->info("plugin_handle: plugin_info(): pModule=%p, pFunc=%p", pModule, pFunc);
	
	//if (pFunc == NULL)
	{
		// Fetch required method in loaded object
		pFunc = PyObject_GetAttrString(pModule, "plugin_info");
		PRINT_FUNC;
		Logger::getLogger()->info("plugin_handle: plugin_info(): pFunc=%p", pFunc);

		if (!pFunc || !PyCallable_Check(pFunc))
		{
			PRINT_FUNC;
			// Failure
			if (PyErr_Occurred())
			{
				logErrorMessage();
			}
			PRINT_FUNC;

			Logger::getLogger()->fatal("Cannot find method plugin_info in loaded python module");
			Py_CLEAR(pFunc);

			return NULL;
		}
	}

	PRINT_FUNC;
	
	// - 2 - Call Python method passing an object
	PyObject* pReturn = PyObject_CallFunction(pFunc, NULL);

	PRINT_FUNC;

	PLUGIN_INFORMATION *info = NULL;

	// - 3 - Handle filter returned data
	if (!pReturn)
	{
		// Errors while getting result object
		Logger::getLogger()->error("Called python script method plugin_info : error while getting result object");

		// Errors while getting result object
		logErrorMessage();

		// Filter did nothing: just pass input data
		info = NULL;
	}
	else
	{
		PRINT_FUNC;
		
		// Get new set of readings from Python filter
		info = Py2C_PluginInfo(pReturn);
		
		// Remove pReturn object
		Py_CLEAR(pReturn);
	}
	if(info)
		Logger::getLogger()->info("plugin_handle: plugin_info(): info={name=%s, version=%s, options=%d, type=%s, interface=%s, config=%s}", 
					info->name, info->version, info->options, info->type, info->interface, info->config);
	return info;
}

#define GET_PLUGIN_INFO_ELEM(elem) \
{ \
		PyObject* item = PyDict_GetItemString(element, #elem);\
		char * elem = new char [string(PyBytes_AsString(item)).length()+1];\
		std::strcpy (elem, string(PyBytes_AsString(item)).c_str());\
		info->elem = elem;\
}

/**
 * Get PLUGIN_INFORMATION structure filled from Python object
 *
 * @param pyRetVal	Python 3.5 Object (dict)
 * @return		Pointer to a new PLUGIN_INFORMATION structure
 *				or NULL in case of errors
 */
PLUGIN_INFORMATION *Py2C_PluginInfo(PyObject* pyRetVal)
{
	// Create returnable PLUGIN_INFORMATION structure
	PLUGIN_INFORMATION *info = new PLUGIN_INFORMATION;

	PyObject *dKey, *dValue;
	Py_ssize_t dPos = 0;
	
	// dKey and dValue are borrowed references
	while (PyDict_Next(pyRetVal, &dPos, &dKey, &dValue))
	{
		 /*if (!PyBytes_Check(dKey) || !PyBytes_Check(dValue))
		  {
			Logger::getLogger()->info("3. PyDict: dKey & dValue are not of required type");
			continue;
		  }*/
		char* ckey = PyUnicode_AsUTF8(dKey);
		char* cval;
		char *emptyStr = new char[1];
		emptyStr[0] = '\0';
		if(strcmp(ckey, "config"))
			cval = PyUnicode_AsUTF8(dValue);
		else
			cval = emptyStr;
		//Logger::getLogger()->info("4. PyDict: dKey=%s, dValue=%s", ckey, cval);

		char *valStr = new char [string(cval).length()+1];
		std::strcpy (valStr, cval);
		
		if(!strcmp(ckey, "name"))
		{
			info->name = valStr;
		}
		else if(!strcmp(ckey, "version"))
		{
			info->version = valStr;
		}
		else if(!strcmp(ckey, "mode"))
		{
			info->options = 0;
			if (!strcmp(valStr, "async"))
			info->options |= SP_ASYNC;
			free(valStr);
		}
		else if(!strcmp(ckey, "type"))
		{
			info->type = valStr;
		}
		else if(!strcmp(ckey, "interface"))
		{
			info->interface = valStr;
		}
		else if(!strcmp(ckey, "config"))
		{
			free (valStr);
			char *valStr1 = new char[3];
			valStr1[0]='{';
			valStr1[1]='}';
			valStr1[2]='\0';
			info->config = valStr1;
			// TODO : write real code : probably convert python dict to JSON string
		}
	}
	
	return info;
}

static void logErrorMessage()
{
	Logger::getLogger()->info("%s:%d", __FUNCTION__, __LINE__);
	//Get error message
	PyObject *pType, *pValue, *pTraceback;
	PyErr_Fetch(&pType, &pValue, &pTraceback);

	// NOTE from :
	// https://docs.python.org/2/c-api/exceptions.html
	//
	// The value and traceback object may be NULL
	// even when the type object is not.	
	const char* pErrorMessage = pValue ?
				    PyBytes_AsString(pValue) :
				    "no error description.";

	Logger::getLogger()->fatal("logErrorMessage: Error '%s' ",
				   pErrorMessage ?
				   pErrorMessage :
				   "no description");

	// Reset error
	PyErr_Clear();

	// Remove references
	Py_CLEAR(pType);
	Py_CLEAR(pValue);
	Py_CLEAR(pTraceback);
}

