'''Injections are dependency injection points: an attribute descriptor,
and a function decorator.
'''
from functools import update_wrapper

from inject.exc import NoParamError
from inject.injectors import get_instance as _get_instance
from inject.utils import get_attrname_by_value


'''
@var super_param: empty object which is used to specify that a param 
    is injected in a super class.
'''
super_param = object()


class InjectionPoint(object):
    
    '''InjectionPoint serves injection requests.'''
    
    __slots__ = ('type', 'none')
    
    def __init__(self, type, none=False):
        self.type = type
        self.none = none
    
    def get_instance(self):
        '''Return an instance for the injection point type.'''
        return _get_instance(self.type, none=self.none)


class AttributeInjection(object):
    
    '''AttributeInjection is a descriptor, which injects an instance into
    an attribute.
    
    Example::
        
        class A(object): pass
        class B(object):
            a = AttributeInjection(A)
    
    '''
    
    def __init__(self, type, reinject=False, none=False):
        '''Create an injection for an attribute.'''
        self.attr = None
        self.reinject = reinject
        
        self.injection = InjectionPoint(type, none)
    
    def __get__(self, instance, owner):
        if instance is None:
            return self
        
        attr = self.attr
        if attr is None:
            attr = self._get_set_attr(owner)
        
        obj = self.injection.get_instance()
        
        if not self.reinject:
            setattr(instance, attr, obj)
        return obj
    
    def _get_set_attr(self, owner):
        attr = get_attrname_by_value(owner, self)
        self.attr = attr
        return attr


class NamedAttributeInjection(object):
    
    '''NamedAttributeInjection is a descriptor, which injects a dependency into
    a specified class attribute.
    
    Example::
        
        class A(object): pass
        class B(object):
            a = NamedAttributeInjection('a', A)
    
    '''
    
    def __init__(self, attr, type, reinject=False, none=False):
        '''Create an injection for an attribute.'''
        self.attr = attr
        self.reinject = reinject
        
        self.injection = InjectionPoint(type, none)
    
    def __get__(self, instance, owner):
        if instance is None:
            return self
        
        attr = self.attr
        obj = self.injection.get_instance()
        
        if not self.reinject:
            setattr(instance, attr, obj)
        return obj


class ClassAttributeInjection(object):
    
    '''ClassAttributeInjection is a class descriptor, which resolves
    a dependency every time it is accessed.
    '''
    
    point_class = InjectionPoint
    
    def __init__(self, type, none=False):
        self.injection = InjectionPoint(type, none)
    
    def __get__(self, instance, owner):
        return self.injection.get_instance()


class ParamInjection(object):
    
    '''ParamInjection is a function decorator, which injects the required
    non-given params directly into a function, passing them as keyword args.
    
    Set an argument to C{super_param} to indicate that it is injected in
    a super class.
    
    Example::
        
        class A(object): pass
        class B(object):
            @ParamInjection('a', A)
            def __init__(self, a):
                self.a = a
        
        class C(B):
            @ParamInjection('a2', A):
            def __init__(self, a2, a=super_param):
                super(C, self).__init__(a)
                self.a2 = a2
        
    '''
    
    def __new__(cls, name, type=None, none=False):
        '''Create a decorator injection for a param.'''
        if type is None:
            type = name
        
        injection = InjectionPoint(type, none)
        
        def decorator(func):
            if getattr(func, 'injection_wrapper', False):
                # It is already a wrapper.
                wrapper = func
            else:
                wrapper = cls.create_wrapper(func)
            cls.add_injection(wrapper, name, injection)
            return wrapper
        
        return decorator
    
    @classmethod
    def create_wrapper(cls, func):
        injections = {}
        
        def injection_wrapper(*args, **kwargs):
            '''InjectionPoint wrapper gets non-existent keyword arguments
            from injections, combines them with kwargs, and passes to
            the wrapped function.
            '''
            for name in injections:
                if name in kwargs and kwargs[name] is not super_param:
                    continue
                
                injection = injections[name]
                kwargs[name] = injection.get_instance()
            
            return func(*args, **kwargs)
        
        # Store the attributes in a wrapper for other functions.
        # Inside the wrapper access them from the closure.
        # It is about 10% faster.
        injection_wrapper.func = func
        injection_wrapper.injections = injections
        injection_wrapper.injection_wrapper = True
        update_wrapper(injection_wrapper, func)
        
        return injection_wrapper
    
    @classmethod
    def add_injection(cls, wrapper, name, injection):
        func = wrapper.func
        func_code = func.func_code
        flags = func_code.co_flags
        
        if not flags & 0x04 and not flags & 0x08:
            # 0x04 func uses args
            # 0x08 func uses kwargs
            varnames = func_code.co_varnames
            if name not in varnames:
                raise NoParamError(
                    '%s does not accept an injected param "%s".' % 
                    (func, name))
        
        wrapper.injections[name] = injection


attr = AttributeInjection
named_attr = NamedAttributeInjection
class_attr = ClassAttributeInjection
param = ParamInjection
