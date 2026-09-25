"""Owned CharacterLab authoring; invoke through the lab editor bridge only.

Operations: inspect, prepare, request, resume, assemble, checkpoint_existing.
Pass character BB_AthleteA/B.
request explicitly starts Epic's cloud rig/texture services, without handling
authentication. A slate observer keeps editing alive and saves when both finish.
Timeout preserves that session; resume observes it without repeating requests.
"""
from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import json
import shutil
import time
import traceback
import uuid

_spec = importlib.util.spec_from_file_location('bb_human_design', Path(__file__).with_name('stage_human_players.py'))
design = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(design)
KEY = '_bb_human_cloud_build'
GARMENT = '/MetaHumanCharacter/Optional/Clothing/WI_DefaultGarment'
ASSEMBLED = '/Game/BasketbroomHumans/Assembled'
ASSEMBLY_OWNER = 'Basketbroom.HumanPlayerAssembly.v1'


def baked_groom_packages(name):
    return {ASSEMBLED+'/'+name+'/T_PreBakedGroom_'+kind+'_'+lod
            for kind in ('Color','NSR') for lod in ('LOD3','LOD5to7')}


def release_baked_groom_scratch(ue,name,packages):
    # Installed MetaHumanDefaultEditorPipelineBase.cpp:1112-1117 explicitly
    # AssetDeletes these intermediates and clears RF_Public|RF_Standalone after
    # baking them into the exported face maps. Never restore flags or save them.
    scratch=set(packages)&baked_groom_packages(name)
    if not scratch: return []
    registry=ue.AssetRegistryHelpers.get_asset_registry()
    options=ue.AssetRegistryDependencyOptions(include_soft_package_references=True,include_hard_package_references=True,
        include_searchable_names=False,include_soft_management_references=False,include_hard_management_references=False)
    for package in scratch:
        if registry.get_assets_by_package_name(package) or registry.get_referencers(package,options):
            raise RuntimeError('Expected discarded, unreferenced groom intermediate: '+package)
    ue.SystemLibrary.collect_garbage()
    return sorted(scratch)


def validate(ue, name):
    current = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.get_project_file_path())).resolve()
    if current != design.PROJECT.resolve() or not ue.SystemLibrary.get_engine_version().startswith('5.8.'):
        raise RuntimeError('Only the isolated BasketbroomCharacterLab UE5.8 project is supported')
    if name not in design.PRESETS: raise ValueError('Choose BB_AthleteA or BB_AthleteB')
    if ue.get_editor_subsystem(ue.LevelEditorSubsystem).is_in_play_in_editor(): raise RuntimeError('Stop lab Play first')
    character = ue.EditorAssetLibrary.load_asset(design.DESTINATION + name)
    if not isinstance(character, ue.MetaHumanCharacter) or not design.owns_collection(character):
        raise RuntimeError('Owned design with its own collection required')
    if ue.EditorAssetLibrary.get_metadata_tag(character, 'BB.Generator') != design.OWNER or ue.EditorAssetLibrary.get_metadata_tag(character, 'BB.SourcePreset') != design.PRESETS[name]:
        raise RuntimeError('Refusing an unrelated design')
    return character, ue.get_editor_subsystem(ue.MetaHumanCharacterEditorSubsystem)


def require_clean(ue):
    dirty = list(ue.EditorLoadingAndSavingUtils.get_dirty_map_packages()) + list(ue.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    if dirty: raise RuntimeError('Save existing lab work first: ' + str([p.get_path_name() for p in dirty]))


def slots(collection):
    return [{'slot':str(row.selection.slot_name), 'item':row.selection.selected_item.to_asset_name_string()}
            for row in collection.default_instance.get_slot_selection_data()]


def checkpoint(ue, character):
    if not ue.EditorAssetLibrary.save_loaded_asset(character, only_if_is_dirty=False):
        raise RuntimeError('Could not save the exact owned design')


def begin(ue, name, character, subsystem, operation):
    existing = getattr(ue, KEY, None)
    if existing and not existing.finished: raise RuntimeError('A lab cloud session is already retained; inspect or resume it first')
    require_clean(ue)
    # The editor toolkit owns its edit session; close only this owned asset.
    ue.get_editor_subsystem(ue.AssetEditorSubsystem).close_all_editors_for_asset(character)
    require_clean(ue)
    if subsystem.is_object_added_for_editing(character):
        raise RuntimeError('The owned character window is still closing. Wait for it to disappear, then retry; no cloud request has been sent and its edit session is preserved')
    # A finished observer is no longer needed. Collect only after confirming
    # there is no active cloud work, asset editor, or unsaved lab content.
    if existing and existing.finished:
        delattr(ue,KEY)
        existing=None
    ue.SystemLibrary.collect_garbage()
    attempt = design.LAB/'build-receipts'/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'-'+uuid.uuid4().hex[:8])
    attempt.mkdir(parents=True, exist_ok=False)
    backup = attempt/'backup'; backup.mkdir()
    original = design.LAB/'Content/BasketbroomHumans/Design'/name
    hashes = {}
    for suffix in design.ASSET_SUFFIXES:
        path = original.with_suffix(suffix)
        if path.is_file():
            shutil.copy2(path, backup/path.name)
            hashes[path.name] = design.digest(path)
            if design.digest(backup/path.name) != hashes[path.name]: raise RuntimeError('Character backup verification failed')
    if name+'.uasset' not in hashes: raise RuntimeError('Saved character asset missing before backup')
    report = {'operation':operation,'character':character.get_path_name(),'status':'starting',
              'backup':str(backup),'backup_hashes':hashes,'cloud_requests_made':False,
              'game_integration_performed':False,'report':str(attempt/'result.json')}
    design.write(attempt/'result.json',report)
    if not subsystem.try_add_object_to_edit(character): raise RuntimeError('Could not register the owned character for editing')
    return attempt, report


def prepare(ue, name, character, subsystem):
    attempt, report = begin(ue,name,character,subsystem,'prepare')
    try:
        collection = subsystem.get_preview_collection(character)
        if collection is None: raise RuntimeError('No editable preview collection')
        report['slots_before'] = slots(collection)
        selections = [row.selection for row in collection.default_instance.get_slot_selection_data()
                      if str(row.selection.slot_name) == 'Outfits']
        if len(selections) > 1: raise RuntimeError('Review multiple existing outfit selections before changing them')
        if not selections:
            wardrobe = ue.EditorAssetLibrary.load_asset(GARMENT)
            if wardrobe is None: raise RuntimeError('Installed default garment is unavailable')
            item_key = collection.try_add_item_from_wardrobe_item(slot_name='Outfits', wardrobe_item=wardrobe)
            if item_key is None: raise RuntimeError('Could not add the default garment')
            selected = ue.MetaHumanPipelineSlotSelection(slot_name='Outfits', selected_item=item_key)
            if not collection.default_instance.try_add_slot_selection(selection=selected): raise RuntimeError('Could not select garment')
        else: item_key = selections[0].selected_item
        subsystem.on_edit_preview_collection(character)
        subsystem.assemble_for_preview(character=character)
        params = collection.default_instance.get_instance_parameters(item_path=ue.MetaHumanPaletteItemPath(item_key=item_key))
        report['outfit_parameters'] = [{'name':str(p.name),'type':str(p.type)} for p in params]
        shirt = next((p for p in params if str(p.name) == 'PrimaryColorShirt'), None)
        if shirt is None or shirt.type != ue.MetaHumanCharacterInstanceParameterType.COLOR:
            raise RuntimeError('Selected garment has no supported PrimaryColorShirt parameter')
        team = 'Teal' if name == 'BB_AthleteA' else 'Copper'
        recipe = json.loads((design.ROOT/'SourceArt/Characters/player_uniforms.json').read_text(encoding='utf-8'))
        color_hex = recipe['teams'][team]['color_srgb']
        def linear(v):
            v = int(v,16)/255.0
            return v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4
        rgb = [linear(color_hex[i:i+2]) for i in (0,2,4)]
        shirt.set_color(value=ue.LinearColor(*rgb,1.0))
        actual = shirt.get_color()
        if any(abs(a-b)>1e-5 for a,b in zip((actual.r,actual.g,actual.b),rgb)):
            raise RuntimeError('Garment color readback mismatch')
        subsystem.on_edit_preview_collection(character)
        report['slots_after'] = slots(collection)
        if [s for s in report['slots_before'] if s['slot'] != 'Outfits'] != [s for s in report['slots_after'] if s['slot'] != 'Outfits']:
            raise RuntimeError('Unexpected change to hair or other preset selections')
        checkpoint(ue,character)
        report.update(status='garment_prepared',shirt_color_srgb=color_hex,team_palette=team)
    except Exception:
        report.update(status='failed',error=traceback.format_exc())
        raise
    finally:
        if subsystem.is_object_added_for_editing(character): subsystem.remove_object_to_edit(character)
        design.write(attempt/'result.json',report)
    return report


class CloudObserver:
    def __init__(self, ue, character, subsystem, attempt, report, timeout):
        self.ue, self.character, self.subsystem = ue, character, subsystem
        self.attempt, self.report = attempt, report
        self.timeout, self.started, self.last = timeout, time.monotonic(), 0
        self.handle, self.finished = None, False

    def save_report(self):
        design.write(self.attempt/'result.json',self.report)
        design.write(design.LAB/'latest-human-build.json',{'report':self.report['report'],'status':self.report['status']})

    def stop_observing(self):
        if self.handle is not None:
            self.ue.unregister_slate_post_tick_callback(self.handle)
            self.handle = None

    def tick(self, _delta):
        now = time.monotonic()
        if now-self.last < 5: return
        self.last = now
        try:
            if not self.subsystem.is_object_added_for_editing(self.character):
                raise RuntimeError('Character edit session disappeared before cloud completion')
            ready = bool(self.subsystem.can_build_meta_human(self.character))
            self.report.update(can_build_meta_human=ready,
                has_high_resolution_textures=bool(self.character.has_high_resolution_textures),
                elapsed_seconds=round(now-self.started,1))
            if ready:
                checkpoint(self.ue,self.character)
                self.subsystem.remove_object_to_edit(self.character)
                self.finished = True
                self.report.update(status='ready_for_assembly',design_saved=True,edit_session_retained=False)
                self.stop_observing()
            elif now-self.started > self.timeout:
                self.report.update(status='needs_attention',edit_session_retained=True,
                    note='Cloud readiness was not reached. Inspect Epic authentication/service notifications; no failure or cancellation is inferred. Resume observes without repeating requests.')
                self.stop_observing()
            self.save_report()
        except Exception:
            self.report.update(status='needs_attention',error=traceback.format_exc(),edit_session_retained=True)
            self.stop_observing(); self.save_report()


def request(ue, name, character, subsystem, timeout):
    attempt, report = begin(ue,name,character,subsystem,'request')
    observer = CloudObserver(ue,character,subsystem,attempt,report,timeout)
    setattr(ue,KEY,observer)
    try:
        if subsystem.can_build_meta_human(character):
            observer.tick(0)
            return report
        # Keep strong references and the edit registration until both services
        # succeed. These reflected methods return before their cloud callbacks.
        report.update(status='waiting_for_cloud',cloud_requests_made=True,edit_session_retained=True,
                      note='Epic may request user sign-in. The tool does not handle authentication.')
        observer.save_report()
        rig = ue.MetaHumanCharacterAutoRiggingRequestParams()
        rig.blocking = False; rig.report_progress = True
        rig.rig_type = ue.MetaHumanRigType.JOINTS_ONLY
        subsystem.request_auto_rigging(character,rig)
        textures = ue.MetaHumanCharacterTextureRequestParams()
        textures.blocking = False; textures.report_progress = True
        subsystem.request_texture_sources(character,textures)
        observer.handle = ue.register_slate_post_tick_callback(observer.tick)
    except Exception:
        report.update(status='needs_attention',error=traceback.format_exc(),edit_session_retained=True,
                      note='A request may already be in flight. Do not repeat it or discard this edit session.')
        observer.save_report()
        raise
    return report


def assemble(ue, name, character, subsystem):
    # The installed 5.8 MetaHumanCharacterBuild.cpp explicitly performs build,
    # unpack and assembly synchronously. Its public method returns no success
    # value, so inspect generated assets and BP compile status before saving.
    assets = ue.EditorAssetLibrary
    target = ASSEMBLED+'/'+name
    common_dir = design.LAB/'Content/BasketbroomHumans/Assembled/Common'
    manifest = design.LAB/'assembly-manifest.json'
    if assets.list_assets(target,recursive=True,include_folder=False):
        raise RuntimeError('Preserve existing assembly; this operation only creates a new athlete output')
    prior = json.loads(manifest.read_text(encoding='utf-8')) if manifest.is_file() else {}
    common_before = design.file_tree(common_dir,design.ASSET_SUFFIXES)
    if common_before and (prior.get('owner') != ASSEMBLY_OWNER or prior.get('common_hashes') != common_before):
        raise RuntimeError('Existing shared MetaHuman assets do not match our saved assembly manifest')
    attempt, report = begin(ue,name,character,subsystem,'assemble')
    try:
        if not subsystem.can_build_meta_human(character): raise RuntimeError('Cloud rig and textures are not ready for assembly')
        if common_before:
            shutil.copytree(common_dir,attempt/'backup-common')
            if design.file_tree(attempt/'backup-common',design.ASSET_SUFFIXES) != common_before:
                raise RuntimeError('Shared MetaHuman asset backup verification failed')
        params = ue.MetaHumanCharacterEditorBuildParameters()
        params.pipeline_type = ue.MetaHumanDefaultPipelineType.OPTIMIZED
        params.pipeline_quality = ue.MetaHumanQualityLevel.MEDIUM
        params.absolute_build_path = ASSEMBLED
        params.common_folder_path = ASSEMBLED+'/Common'
        params.enable_wardrobe_item_validation = True
        report.update(status='assembling',pipeline='OPTIMIZED',quality='MEDIUM',output=target)
        design.write(attempt/'result.json',report)
        subsystem.build_meta_human(character=character,params=params)
        blueprint_path = target+'/BP_'+name
        blueprint = assets.load_asset(blueprint_path)
        if not isinstance(blueprint,ue.Blueprint) or blueprint.generated_class() is None:
            raise RuntimeError('Assembly did not produce the expected actor Blueprint')
        # This engine tag is written only after unpacking dependencies and
        # updating the actor from its assembled instance, near the end of build.
        export_quality = assets.get_metadata_tag(blueprint,'MHExportQuality')
        if export_quality != 'Medium':
            raise RuntimeError('Assembly did not finish a Medium-quality actor: '+str(export_quality))
        status = blueprint.get_editor_property('status')
        if status not in (ue.BlueprintStatus.BS_UP_TO_DATE,ue.BlueprintStatus.BS_UP_TO_DATE_WITH_WARNINGS):
            raise RuntimeError('Assembled Blueprint has not compiled successfully: '+str(status))
        paths = sorted(set(assets.list_assets(target,recursive=True,include_folder=False)) |
                       set(assets.list_assets(ASSEMBLED+'/Common',recursive=True,include_folder=False)))
        loaded = [assets.load_asset(p) for p in paths]
        if any(a is None for a in loaded): raise RuntimeError('An assembled asset could not be loaded')
        meshes = [a for a in loaded if isinstance(a,ue.SkeletalMesh) and a.get_path_name().startswith(target+'/')]
        if not meshes: raise RuntimeError('No character skeletal meshes were generated')
        report['skeletal_meshes'] = [a.get_path_name() for a in meshes]
        dirty = list(ue.EditorLoadingAndSavingUtils.get_dirty_map_packages()) + list(ue.EditorLoadingAndSavingUtils.get_dirty_content_packages())
        allowed = (target+'/',ASSEMBLED+'/Common/')
        unexpected = [p.get_path_name() for p in dirty if p.get_path_name() != design.DESTINATION+name and not p.get_path_name().startswith(allowed)]
        if unexpected: raise RuntimeError('Assembly dirtied unexpected packages; preserve for inspection: '+str(unexpected))
        assets.set_metadata_tag(blueprint,'BB.Generator',ASSEMBLY_OWNER)
        assets.set_metadata_tag(blueprint,'BB.SourceDesign',character.get_path_name())
        if not assets.save_loaded_assets(loaded,only_if_is_dirty=True): raise RuntimeError('Could not save the exact generated asset set')
        report['saved_assets'] = [asset.get_path_name() for asset in loaded]
        if any(p.get_path_name() == design.DESTINATION+name for p in ue.EditorLoadingAndSavingUtils.get_dirty_content_packages()):
            checkpoint(ue,character)
        dirty_names=[p.get_path_name() for p in ue.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        dirty=[]  # Release our UPackage wrappers before normal engine GC.
        report['discarded_groom_intermediates']=release_baked_groom_scratch(ue,name,dirty_names)
        remaining=[p.get_path_name() for p in ue.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        if set(remaining)-set(report['discarded_groom_intermediates']):
            raise RuntimeError('Generated content is still unsaved: '+str(remaining))
        # The build's call stack can retain discarded objects through this tick.
        # They are not exported assets, so do not falsely call the saved assembly
        # a failure. A later checkpoint_existing call can collect them again.
        report['cleanup_deferred_to_next_tick']=bool(remaining)
        report['pending_intermediate_packages']=remaining
        prior.update(owner=ASSEMBLY_OWNER,common_hashes=design.file_tree(common_dir,design.ASSET_SUFFIXES))
        prior.setdefault('characters',{})[name] = {'blueprint':blueprint_path,'report':report['report'],
            'files':design.file_tree(design.LAB/'Content/BasketbroomHumans/Assembled'/name,design.ASSET_SUFFIXES)}
        design.write(manifest,prior)
        report.update(status='assembled_pending_visual_review',blueprint=blueprint_path,blueprint_status=str(status),export_quality=export_quality)
    except Exception:
        report.update(status='failed',error=traceback.format_exc())
        raise
    finally:
        if subsystem.is_object_added_for_editing(character): subsystem.remove_object_to_edit(character)
        design.write(attempt/'result.json',report)
        design.write(design.LAB/'latest-human-build.json',{'report':report['report'],'status':report['status']})
    return report


def checkpoint_existing(ue,name,character,source_receipt):
    source=Path(source_receipt).resolve()
    source.relative_to((design.LAB/'build-receipts').resolve())
    prior_attempt=json.loads(source.read_text(encoding='utf-8'))
    recoverable=prior_attempt.get('status')=='failed' or prior_attempt.get('cleanup_deferred_to_next_tick') is True
    if prior_attempt.get('operation')!='assemble' or not recoverable or prior_attempt.get('character')!=character.get_path_name():
        raise RuntimeError('Recovery requires this exact failed assembly receipt')
    if not prior_attempt.get('saved_assets'): raise RuntimeError('No saved assembly outputs recorded for this recovery')
    if ue.EditorLoadingAndSavingUtils.get_dirty_map_packages(): raise RuntimeError('Preserve unsaved map work')
    active=getattr(ue,KEY,None)
    if active and not active.finished: raise RuntimeError('Wait for the active cloud session')
    assets=ue.EditorAssetLibrary; target=ASSEMBLED+'/'+name
    blueprint_path=target+'/BP_'+name
    blueprint=assets.load_asset(blueprint_path)
    if not isinstance(blueprint,ue.Blueprint) or assets.get_metadata_tag(blueprint,'BB.Generator')!=ASSEMBLY_OWNER or assets.get_metadata_tag(blueprint,'MHExportQuality')!='Medium':
        raise RuntimeError('Expected the owned completed Medium actor')
    if blueprint.generated_class() is None or blueprint.get_editor_property('status') not in (ue.BlueprintStatus.BS_UP_TO_DATE,ue.BlueprintStatus.BS_UP_TO_DATE_WITH_WARNINGS):
        raise RuntimeError('The generated actor is not successfully compiled')
    paths=sorted(set(assets.list_assets(target,recursive=True,include_folder=False)) |
                 set(assets.list_assets(ASSEMBLED+'/Common',recursive=True,include_folder=False)))
    if set(paths)!=set(prior_attempt['saved_assets']): raise RuntimeError('Current output set differs from the interrupted save receipt')
    dirty=list(ue.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    allowed={p.split('.')[0] for p in paths}
    allowed.update(baked_groom_packages(name))
    if any(p.get_path_name() not in allowed for p in dirty): raise RuntimeError('Unexpected unsaved content; this recovery saves only generated outputs: '+str([p.get_path_name() for p in dirty]))
    attempt=design.LAB/'build-receipts'/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'-'+uuid.uuid4().hex[:8])
    attempt.mkdir(parents=True,exist_ok=False)
    report={'operation':'checkpoint_existing','status':'saving','character':character.get_path_name(),
            'source_receipt':str(source),'report':str(attempt/'result.json'),'blueprint':blueprint_path,
            'dirty_before':[p.get_path_name() for p in dirty],'rebuilt':False,'assets_deleted':False}
    design.write(attempt/'result.json',report)
    try:
        for package in report['dirty_before']:
            original=design.LAB/'Content'/package.removeprefix('/Game/')
            for suffix in design.ASSET_SUFFIXES:
                filename=original.with_suffix(suffix)
                if filename.exists():
                    backup=attempt/'backup'/filename.relative_to(design.LAB/'Content')
                    backup.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(filename,backup)
                    if design.digest(filename)!=design.digest(backup): raise RuntimeError('Recovery backup verification failed')
        real_dirty=[p for p in report['dirty_before'] if p not in baked_groom_packages(name)]
        loaded=[assets.load_asset(p) for p in real_dirty]
        if any(a is None for a in loaded): raise RuntimeError('Could not load an exact dirty output')
        if loaded and not assets.save_loaded_assets(loaded,only_if_is_dirty=True): raise RuntimeError('Could not checkpoint generated textures')
        dirty=[]  # A Python UPackage wrapper must not keep scratch packages alive.
        report['discarded_groom_intermediates']=release_baked_groom_scratch(ue,name,report['dirty_before'])
        remaining=[p.get_path_name() for p in ue.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        if remaining: raise RuntimeError('Unsaved packages remain: '+str(remaining))
        for object_path in set(paths)|set(real_dirty):
            filename=design.LAB/'Content'/(object_path.split('.')[0].removeprefix('/Game/')+'.uasset')
            if not filename.is_file(): raise RuntimeError('Missing saved assembly package: '+str(filename))
        manifest=design.LAB/'assembly-manifest.json'
        state=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {'owner':ASSEMBLY_OWNER,'characters':{}}
        if state.get('owner')!=ASSEMBLY_OWNER: raise RuntimeError('Unrelated assembly manifest')
        state['common_hashes']=design.file_tree(design.LAB/'Content/BasketbroomHumans/Assembled/Common',design.ASSET_SUFFIXES)
        state['characters'][name]={'blueprint':blueprint_path,'report':report['report'],
            'files':design.file_tree(design.LAB/'Content/BasketbroomHumans/Assembled'/name,design.ASSET_SUFFIXES)}
        design.write(manifest,state)
        report.update(status='assembled_pending_visual_review',saved_assets=real_dirty,dirty_after=[])
    except Exception:
        report.update(status='failed',error=traceback.format_exc()); raise
    finally:
        design.write(attempt/'result.json',report)
        design.write(design.LAB/'latest-human-build.json',{'report':report['report'],'status':report['status']})
    return report


def run(operation='inspect', name='BB_AthleteA', timeout=900,source_receipt=None):
    import unreal as ue
    character, subsystem = validate(ue,name)
    if operation == 'inspect':
        active = getattr(ue,KEY,None)
        return {'character':design.describe_character(ue,character),
                'slots':slots(character.get_editor_property('internal_collection')),
                'active_cloud_session':active.report if active else None}
    if operation == 'prepare': return prepare(ue,name,character,subsystem)
    if operation == 'request': return request(ue,name,character,subsystem,min(max(float(timeout),60),1800))
    if operation == 'assemble': return assemble(ue,name,character,subsystem)
    if operation == 'checkpoint_existing': return checkpoint_existing(ue,name,character,source_receipt)
    if operation == 'resume':
        active = getattr(ue,KEY,None)
        if active is None or active.finished or active.character != character: raise RuntimeError('No matching retained cloud session')
        if active.handle is not None: return active.report
        if not subsystem.is_object_added_for_editing(character): raise RuntimeError('Cannot resume a lost edit session')
        active.started=time.monotonic(); active.last=0
        active.report.update(status='waiting_for_cloud',note='Observing existing requests; no new cloud request sent')
        active.handle=ue.register_slate_post_tick_callback(active.tick)
        active.save_report()
        return active.report
    raise ValueError('Choose inspect, prepare, request, resume, assemble, or checkpoint_existing')


if __name__ == '__main__':
    args=globals().get('BRIDGE_ARGS',{})
    RESULT=run(args.get('operation','inspect'),args.get('character','BB_AthleteA'),args.get('timeout_seconds',900),args.get('source_receipt'))
