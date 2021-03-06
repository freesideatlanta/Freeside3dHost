'''OpenGL extension EXT.texture_perturb_normal

Automatically generated by the get_gl_extensions script, do not edit!
'''
from OpenGL import platform, constants, constant, arrays
from OpenGL import extensions
from OpenGL.GL import glget
import ctypes
EXTENSION_NAME = 'GL_EXT_texture_perturb_normal'
_DEPRECATED = False
GL_PERTURB_EXT = constant.Constant( 'GL_PERTURB_EXT', 0x85AE )
GL_TEXTURE_NORMAL_EXT = constant.Constant( 'GL_TEXTURE_NORMAL_EXT', 0x85AF )
glTextureNormalEXT = platform.createExtensionFunction( 
'glTextureNormalEXT',dll=platform.GL,
extension=EXTENSION_NAME,
resultType=None, 
argTypes=(constants.GLenum,),
doc='glTextureNormalEXT(GLenum(mode)) -> None',
argNames=('mode',),
deprecated=_DEPRECATED,
)


def glInitTexturePerturbNormalEXT():
    '''Return boolean indicating whether this extension is available'''
    return extensions.hasGLExtension( EXTENSION_NAME )
