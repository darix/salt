'''
Template render systems
'''
from __future__ import absolute_import

# Import python libs
import codecs
import os
import imp
import logging
import tempfile
import traceback

# Import salt libs
import salt.utils

logger = logging.getLogger(__name__)

class SaltTemplateRenderError(Exception):
    pass

utf_8_encode = codecs.getencoder('utf-8') # this one has no BOM.

def wrap_tmpl_func(render_str):
    def render_tmpl(source, from_str=False, to_str=False, context=None, **kws):
        if context is None:
            context = {}
        context.update(kws)
        assert 'opts' in context
        assert 'env' in context
        if isinstance(source, basestring):
            if from_str:
                tmplstr = source
            else:
                with codecs.open(source, 'r', encoding='utf-8') as tmplsrc:
                    tmplstr = tmplsrc.read()
        else: # assume source is file-like.
            tmplstr = source.read()
        try:
            output = render_str(tmplstr, context)
        except SaltTemplateRenderError, exc:
            return dict(result=False, data=str(exc))
        except Exception:
            return dict(result=False, data=traceback.format_exc())
        else:
            if to_str: # then render as string
                return dict(result=True, data=output)
            with tempfile.NamedTemporaryFile('wb', delete=False) as outf:
                outf.write(utf_8_encode(output)[0])
                # Note: If nothing is replaced or added by the rendering
                #       function, then the contents of the output file will
                #       be exactly the same as the input.

    render_tmpl.render_str = render_str
    return render_tmpl



def render_jinja_tmpl(tmplstr, context):
    from jinja2 import Environment, StrictUndefined
    from jinja2.exceptions import TemplateSyntaxError
    from salt.utils.jinja import SaltCacheLoader

    opts = context['opts']
    loader = SaltCacheLoader(opts, context['env'])
    if opts.get('allow_undefined', False):
        env = Environment(loader=loader)
    else:
        env = Environment(loader=loader, undefined=StrictUndefined)
    try:
        return env.from_string(tmplstr).render(**context)
    except TemplateSyntaxError, exc:
        raise SaltTemplateRenderError(str(exc))
#FIXME: what about the newline thing?


def render_mako_tmpl(tmplstr, context):
    import mako.exceptions
    from mako.template import Template
    from salt.utils.mako import SaltMakoTemplateLookup
    try:
        return Template(
            tmplstr,
            strict_undefined=True,
            uri=context['sls'].replace('.', '/') if 'sls' in context else None,
            lookup=SaltMakoTemplateLookup(context['opts'], context['env'])
        ).render(**context)
    except:
        raise SaltTemplateRenderError(
                    mako.exceptions.text_error_template().render())


def render_wempy_tmpl(tmplstr, context):
    from wemplate.wemplate import TemplateParser as Template
    return Template(tmplstr).render(**context)



def py(sfn, string=False, **kwargs):
    '''
    Render a template from a python source file

    Returns::

        {'result': bool,
         'data': <Error data or rendered file path>}
    '''
    if not os.path.isfile(sfn):
        return {}

    mod = imp.load_source(
            os.path.basename(sfn).split('.')[0],
            sfn
            )
    for kwarg in kwargs:
        setattr(mod, kwarg, kwargs[kwarg])

    try:
        data = mod.run()
        if string:
            return {'result': True,
                    'data': data}
        fd_, tgt = tempfile.mkstemp()
        os.close(fd_)
        with open(tgt, 'w+') as target:
            target.write(data)
        return {'result': True,
                'data': tgt}
    except Exception:
        trb = traceback.format_exc()
        return {'result': False,
                'data': trb}


jinja = wrap_tmpl_func(render_jinja_tmpl)
mako = wrap_tmpl_func(render_mako_tmpl)
wempy = wrap_tmpl_func(render_wempy_tmpl)


template_registry = {
    'jinja': jinja,
    'mako': mako,
    'py': py,
    'wempy': wempy,
}
