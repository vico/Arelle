"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, cast

from arelle import ModelDocument
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelObject import ModelObject
from arelle.ModelValue import qname, qnameEltPfxName
from arelle.ValidateXbrl import ValidateXbrl
from arelle.XbrlConst import qnLinkSchemaRef, qnLinkLinkbaseRef, qnLinkRoleRef, qnLinkArcroleRef, qnXbrliContext, qnXbrliUnit, qnEnumerationItemTypes
from arelle import XmlUtil
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import (
    DISCLOSURE_SYSTEM_NT16,
    DISCLOSURE_SYSTEM_NT17,
    DISCLOSURE_SYSTEM_NT18,
)
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

INSTANCE_ELEMENT_ORDER = {
    qnLinkSchemaRef.clarkNotation: 0,
    qnLinkLinkbaseRef.clarkNotation: 1,
    qnLinkRoleRef.clarkNotation: 2,
    qnLinkArcroleRef.clarkNotation: 3,
    qnXbrliContext.clarkNotation: 4,
    qnXbrliUnit.clarkNotation: 5,
    'fact': 6,
}


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18,
    ],
)
def rule_fg_nl_04(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FG-NL-04: An XBRL instance document SHOULD order the elements so that referents precede references.
    The children of the 'xbrli:xbrl' element should appear in the following order:
    1. schemaRef
    2. linkbaseRef
    3. roleRef
    4. arcroleRef
    5. context
    6. units
    7. facts
    """
    errors = defaultdict(list)
    for doc in val.modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            currentName = list(INSTANCE_ELEMENT_ORDER.keys())[0]
            currentIndex = INSTANCE_ELEMENT_ORDER[currentName]
            for elt in doc.xmlRootElement.iter():
                if not isinstance(elt, ModelObject):
                    continue
                if isinstance(elt, ModelFact):
                    thisName = 'fact'
                else:
                    thisName = elt.elementQname.clarkNotation
                if thisName not in INSTANCE_ELEMENT_ORDER:
                    continue
                thisIndex = INSTANCE_ELEMENT_ORDER[thisName]
                if thisIndex == currentIndex:
                    continue
                if thisIndex > currentIndex:
                    currentIndex = thisIndex
                    currentName = thisName
                else:
                    errors[(thisName, currentName)].append(elt)
    for names, elts in errors.items():
        beforeName, afterName = names
        yield Validation.warning(
            codes='NL.FG-NL-04',
            msg=_('"%(beforeName)s" elements should not appear after "%(afterName)s" elements.'),
            modelObject=elts,
            beforeName=qname(beforeName),
            afterName=qname(afterName),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18,
    ],
)
def rule_fg_nl_05(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FG-NL-05: Unused namespace declarations SHOULD NOT exist in a XBRL instance document.
    """
    modelXbrl = val.modelXbrl
    factsByDocument = pluginData.factsByDocument(modelXbrl)
    unitsByDocument = pluginData.unitsByDocument(modelXbrl)
    contextsByDocument = pluginData.contextsByDocument(modelXbrl)

    for doc in modelXbrl.urlDocs.values():
        if doc.type != ModelDocument.Type.INSTANCE:
            continue
        root = doc.xmlRootElement
        prefixes = set(k for k in root.nsmap.keys() if k)
        usedPrefixes = set()

        for elt in root.iter():
            if not isinstance(elt, ModelObject):
                continue
            usedPrefixes.add(elt.qname.prefix)
            for attrTag in elt.keys():
                attrTag = cast(str, attrTag)
                if attrTag.startswith("{"):
                    prefix = XmlUtil.clarkNotationToPrefixNsLocalname(elt, attrTag, isAttribute=True)[0]
                    if prefix:
                        usedPrefixes.add(prefix)
        for context in contextsByDocument.get(doc.filepath, []):
            for dimension in context.qnameDims.values():
                dimensionQname = dimension.dimensionQname
                usedPrefixes.add(dimensionQname.prefix)
                if dimension.isExplicit:
                    memberQname = dimension.memberQname
                else:
                    memberQname = dimension.typedMember.qname
                if memberQname:
                    usedPrefixes.add(memberQname.prefix)
        for fact in factsByDocument.get(doc.filepath, []):
            concept = fact.concept
            if concept.typeQname in qnEnumerationItemTypes:
                enumQname = getattr(fact, "xValue", None) or qnameEltPfxName(fact, fact.value)
                if enumQname:
                    usedPrefixes.add(enumQname.prefix)
        for unit in unitsByDocument.get(doc.filepath, []):
            for measures in unit.measures:
                for measure in measures:
                    usedPrefixes.add(measure.prefix)
        unusedPrefixes = prefixes - usedPrefixes
        if len(unusedPrefixes) > 0:
            yield Validation.warning(
                codes='NL.FG-NL-05',
                msg=_('Unused namespaces found in an instance document: %(unusedPrefixes)s'),
                unusedPrefixes=', '.join([f'{p}: {ns}' for p, ns in root.nsmap.items() if p in unusedPrefixes]),
                modelObject=root,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
        DISCLOSURE_SYSTEM_NT18,
    ],
)
def rule_fg_nl_09(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FG-NL-09: A fact SHOULD NOT contain an 'id' attribute.
    """
    facts = [f for f in val.modelXbrl.facts if f.id is not None]
    if len(facts) > 0:
        yield Validation.warning(
            codes='NL.FG-NL-09',
            msg=_('A fact SHOULD NOT contain an "id" attribute'),
            modelObject=facts,
        )
