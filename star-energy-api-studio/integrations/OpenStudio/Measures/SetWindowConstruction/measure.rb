class SetWindowConstruction < OpenStudio::Measure::ModelMeasure
  def name
    'Set Window Construction'
  end

  def description
    'Assigns a named glazing construction to every exterior window in the model.'
  end

  def modeler_description
    'Updates both the explicit sub-surface assignments and the default sub-surface ' \
      'construction set, so no window keeps the previous glazing through either path.'
  end

  def arguments(_model)
    args = OpenStudio::Measure::OSArgumentVector.new

    target = OpenStudio::Measure::OSArgument.makeStringArgument('target_construction', true)
    target.setDisplayName('Target glazing construction')
    target.setDescription('Name of an existing OS:Construction to apply to windows.')
    target.setDefaultValue('penc_std_4mm')
    args << target

    args
  end

  # Bir alt yuzeyin cam sayilip sayilmadigi. Kapilar ve opak alt yuzeyler
  # disarida birakilir; yalnizca pencere turleri degistirilir.
  GLAZED_TYPES = ['FixedWindow', 'OperableWindow', 'GlassDoor', 'Skylight'].freeze

  def run(model, runner, user_arguments)
    super(model, runner, user_arguments)
    return false unless runner.validateUserArguments(arguments(model), user_arguments)

    target_name = runner.getStringArgumentValue('target_construction', user_arguments)

    optional = model.getConstructionByName(target_name)
    if optional.empty?
      runner.registerError("Construction not found: #{target_name}")
      return false
    end
    construction = optional.get

    unless construction.isFenestration
      runner.registerError("#{target_name} is not a fenestration construction.")
      return false
    end

    changed_subsurfaces = 0
    skipped = 0
    model.getSubSurfaces.each do |sub_surface|
      unless GLAZED_TYPES.include?(sub_surface.subSurfaceType)
        skipped += 1
        next
      end
      existing = sub_surface.construction
      if existing.is_initialized && existing.get.handle == construction.handle
        next
      end
      sub_surface.setConstruction(construction)
      changed_subsurfaces += 1
    end

    # Yuzeye dogrudan atama yapilmamis pencereler varsayilan setten beslenir;
    # o yol guncellenmezse eski cam sessizce kullanilmaya devam eder.
    changed_defaults = 0
    model.getDefaultSubSurfaceConstructionss.each do |default_set|
      %w[FixedWindow OperableWindow GlassDoor Skylight].each do |field|
        setter = "set#{field}Construction"
        getter = "#{field[0].downcase}#{field[1..]}Construction"
        current = default_set.public_send(getter)
        next if current.is_initialized && current.get.handle == construction.handle

        default_set.public_send(setter, construction)
        changed_defaults += 1
      end
    end

    runner.registerInitialCondition(
      "#{model.getSubSurfaces.length} sub-surfaces found; #{skipped} are not glazed."
    )
    runner.registerValue('window_construction', target_name)
    runner.registerValue('windows_changed', changed_subsurfaces, 'count')
    runner.registerFinalCondition(
      "Applied #{target_name} to #{changed_subsurfaces} window(s) and " \
        "#{changed_defaults} default construction field(s)."
    )
    true
  rescue StandardError => e
    runner.registerError("Set Window Construction failed: #{e.message}")
    false
  end
end

SetWindowConstruction.new.registerWithApplication
