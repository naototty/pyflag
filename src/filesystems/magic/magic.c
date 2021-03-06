/*
   Python wrappers for magic functions.

   Copyright (C) Brett Funderburg, Deepfile Corp. Austin, TX, US 2003

   Redistribution and use in source and binary forms, with or without
   modification, are permitted provided that the following conditions
   are met:
   1. Redistributions of source code must retain the above copyright
      notice immediately at the beginning of the file, without modification,
      this list of conditions, and the following disclaimer.
   2. Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
   3. The name of the author may not be used to endorse or promote products
      derived from this software without specific prior written permission.
    
   THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
   ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
   IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
   ARE DISCLAIMED. IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE FOR
   ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
   DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
   OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
   HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
   LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
   OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
   SUCH DAMAGE.
*/

#include <Python.h>
#include <magic.h>

static char _magic_open__doc__[] =
"Returns a magic cookie on success and None on failure.\n";
static PyObject* py_magic_open(PyObject* self, PyObject* args)
{
    int flags = 0;
    magic_t cookie;
    PyObject *result;

    if(!PyArg_ParseTuple(args, "i", &flags))
        return NULL;

    if(!(cookie = magic_open(flags))) {
        PyErr_SetString(PyExc_RuntimeError, "failure initializing magic cookie");
	return NULL;
    }

    result = PyCObject_FromVoidPtr(cookie, (void (*)(void *))magic_close);
    return result;
}

static char _magic_errno__doc__[] =
"Returns a numeric error code. If return value is 0, an internal \
 magic error occurred. If return value is non-zero, the value is \
 an OS error code. Use the errno module or os.strerror() can be used \
 to provide detailed error information.\n";
static PyObject* py_magic_errno(PyObject* self, PyObject* args)
{
    PyObject *pycookie;
    magic_t cookie;

    if(!(PyArg_ParseTuple(args, "O", &pycookie)))
        return NULL;

    cookie = PyCObject_AsVoidPtr(pycookie);
    return PyInt_FromLong(magic_errno(cookie));
}

static char _magic_file__doc__[] =
"Returns a textual description of the contents of the argument passed \
 as a filename or None if an error occurred and the MAGIC_ERROR flag \
 is set. A call to errno() will return the numeric error code.\n";
static PyObject* py_magic_file(PyObject* self, PyObject* args)
{
    char* filename = NULL;
    PyObject *pycookie;
    magic_t cookie;
    const char* message = NULL;
    PyObject* result = Py_None;

    if(!(PyArg_ParseTuple(args, "Os", &pycookie, &filename)))
        return NULL;

    cookie = PyCObject_AsVoidPtr(pycookie);

    message = magic_file(cookie, filename);

    if(message != NULL) {
        result = PyString_FromString(message);
    } else {
    	/** An error occurs we return it now: */
        PyErr_SetString(PyExc_RuntimeError, magic_error(cookie));
	return NULL;
    };
    
    return PyString_FromString(message);
}

static char _magic_buffer__doc__[] =
"Returns a textual description of the contents of the argument passed \
 as a buffer or None if an error occurred and the MAGIC_ERROR flag \
 is set. A call to errno() will return the numeric error code.\n";
static PyObject* py_magic_buffer(PyObject* self, PyObject* args)
{
    PyObject *pycookie;
    magic_t cookie;
    void* buffer = NULL;
    int buffer_length = 0;
    const char* message = NULL;
    PyObject* result = Py_None;

    if(!(PyArg_ParseTuple(args, "Os#", &pycookie, (char**)&buffer, 
    						&buffer_length)))
        return NULL;

    cookie = PyCObject_AsVoidPtr(pycookie);

    message = magic_buffer(cookie, buffer, buffer_length);

    if(message != NULL) {
        result = PyString_FromString(message);
    } else {
    	/** An error occurs we return it now: */
        PyErr_SetString(PyExc_RuntimeError, magic_error(cookie));
	return NULL;
    };
    
    return PyString_FromString(message);
}

static char _magic_setflags__doc__[] =
"Set flags on the cookie object.\n \
 Returns -1 on systems that don't support utime(2) or utimes(2) \
 when MAGIC_PRESERVE_ATIME is set.\n";
static PyObject* py_magic_setflags(PyObject* self, PyObject* args)
{
    PyObject *pycookie;
    magic_t cookie;
    int flags;
    int result;

    if(!(PyArg_ParseTuple(args, "Oi", &pycookie, &flags)))
        return NULL;
	
    cookie = PyCObject_AsVoidPtr(pycookie);

    result = magic_setflags(cookie, flags);

    return PyInt_FromLong(result);
}

static char _magic_check__doc__[] =
"Check the validity of entries in the colon separated list of \
 database files passed as argument or the default database file \
 if no argument.\n Returns 0 on success and -1 on failure.\n";
static PyObject* py_magic_check(PyObject* self, PyObject* args)
{
    PyObject *pycookie;
    magic_t cookie;
    char* filename = NULL;
    int result;

    if(!(PyArg_ParseTuple(args, "O|s", &pycookie, &filename)))
        return NULL;

    cookie = PyCObject_AsVoidPtr(pycookie);

    result = magic_check(cookie, filename);

    return PyInt_FromLong(result);
}

static char _magic_compile__doc__[] =
"Compile entries in the colon separated list of database files \
 passed as argument or the default database file if no argument.\n \
 Returns 0 on success and -1 on failure.\n \
 The compiled files created are named from the basename(1) of each file \
 argument with \".mgc\" appended to it.\n";
static PyObject* py_magic_compile(PyObject* self, PyObject* args)
{
    PyObject *pycookie;
    magic_t cookie;
    char* filename = NULL;
    int result;

    if(!(PyArg_ParseTuple(args, "O|s", &pycookie, &filename)))
        return NULL;

    cookie = PyCObject_AsVoidPtr(pycookie);
    result = magic_compile(cookie, filename);

    return PyInt_FromLong(result);
}

static char _magic_load__doc__[] =
"Must be called to load entries in the colon separated list of database files \
 passed as argument or the default database file if no argument before \
 any magic queries can be performed.\n \
 Returns 0 on success and -1 on failure.\n";
static PyObject* py_magic_load(PyObject* self, PyObject* args)
{
    PyObject *pycookie;
    magic_t cookie;
    char* filename = NULL;
    int result;

    if(!(PyArg_ParseTuple(args, "O|s", &pycookie, &filename)))
        return NULL;

    cookie = PyCObject_AsVoidPtr(pycookie);
    result = magic_load(cookie, filename);

    return PyInt_FromLong(result);
}

/* object methods */

static PyMethodDef magic_cookie_hnd_methods[] = {
};

/* module level methods */

static PyMethodDef magic_methods[] = {
    { "open", (PyCFunction)py_magic_open,
      METH_VARARGS, _magic_open__doc__ },
    { "file", (PyCFunction)py_magic_file,
      METH_VARARGS, _magic_file__doc__ },
    { "buffer", (PyCFunction)py_magic_buffer,
      METH_VARARGS, _magic_buffer__doc__ },
    { "setflags", (PyCFunction)py_magic_setflags,
      METH_VARARGS, _magic_setflags__doc__ },
    { "check", (PyCFunction)py_magic_check,
      METH_VARARGS, _magic_check__doc__ },
    { "compile", (PyCFunction)py_magic_compile,
      METH_VARARGS, _magic_compile__doc__ },
    { "load", (PyCFunction)py_magic_load,
      METH_VARARGS, _magic_load__doc__ },
    { "errno", (PyCFunction)py_magic_errno,
      METH_NOARGS, _magic_errno__doc__ },
    { NULL, NULL }
};

/* Initialize constants */

static struct const_vals {
    const char* const name;
    unsigned int value;
} module_const_vals[] = {
    { "MAGIC_NONE", MAGIC_NONE },
    { "MAGIC_DEBUG", MAGIC_DEBUG },
    { "MAGIC_SYMLINK", MAGIC_SYMLINK },
    { "MAGIC_COMPRESS", MAGIC_COMPRESS },
    { "MAGIC_DEVICES", MAGIC_DEVICES },
    { "MAGIC_MIME", MAGIC_MIME },
    { "MAGIC_CONTINUE", MAGIC_CONTINUE },
    { "MAGIC_CHECK", MAGIC_CHECK },
    { "MAGIC_PRESERVE_ATIME", MAGIC_PRESERVE_ATIME },
    { "MAGIC_ERROR", MAGIC_ERROR},
    { NULL }
};

static void const_init(PyObject* dict)
{
    struct const_vals* tmp;
    PyObject *obj;

    for(tmp = module_const_vals; tmp->name; ++tmp) {
        obj = PyInt_FromLong(tmp->value);
        PyDict_SetItemString(dict, tmp->name, obj);
        Py_DECREF(obj);
    }
}

/*
 * Module initialization
 */

void initmagic(void)
{
    PyObject* module;
    PyObject* dict;

    /* Initialize module */

    module = Py_InitModule("magic", magic_methods);
    dict = PyModule_GetDict(module);

    /* Initialize constants */

    const_init(dict);

    if(PyErr_Occurred())
        Py_FatalError("can't initialize module magic");
}
