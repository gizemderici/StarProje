class SetInfiltrationRate < OpenStudio::Measure::ModelMeasure
  def name
    'Set Infiltration Rate'
  end

  def description
    'Scales every space infiltration object by a single multiplier.'
  end

  def modeler_description
    'The model mixes AirChanges/Hour and Flow/ExteriorArea objects, so the measure ' \
      'reads whichever calculation method each object actually uses and scales that ' \
      'value. The multiplier is relative to the seed model, which every run starts from.'
  end

  def arguments(_model)
    args = OpenStudio::Measure::OSArgumentVector.new

    multiplier = OpenStudio::Measure::OSArgument.makeDoubleArgument('infiltration_multiplier', true)
    multiplier.setDisplayName('Infiltration multiplier')
    multiplier.setDescription('1.0 keeps the seed model rates; 0.5 halves them.')
    multiplier.setDefaultValue(1.0)
    args << multiplier

    args
  end

  # Her nesne icin yalnizca bir hesap yontemi tanimlidir; okuyucu ve yazici
  # ciftleri sirayla denenir ve ilk tanimli olan olceklenir.
  METHODS = [
    [:designFlowRate,               :setDesignFlowRate,              'Flow/Space'],
    [:flowperSpaceFloorArea,        :setFlowperSpaceFloorArea,       'Flow/Area'],
    [:flowperExteriorSurfaceArea,   :setFlowperExteriorSurfaceArea,  'Flow/ExteriorArea'],
    [:flowperExteriorWallArea,      :setFlowperExteriorWallArea,     'Flow/ExteriorWallArea'],
    [:airChangesperHour,            :setAirChangesperHour,           'AirChanges/Hour']
  ].freeze

  def run(model, runner, user_arguments)
    super(model, runner, user_arguments)
    return false unless runner.validateUserArguments(arguments(model), user_arguments)

    multiplier = runner.getDoubleArgumentValue('infiltration_multiplier', user_arguments)
    if multiplier <= 0
      runner.registerError('Infiltration multiplier must be greater than zero.')
      return false
    end

    objects = model.getSpaceInfiltrationDesignFlowRates
    if objects.empty?
      runner.registerError('No OS:SpaceInfiltration:DesignFlowRate objects found.')
      return false
    end

    if (multiplier - 1.0).abs < 1e-9
      runner.registerAsNotApplicable("Multiplier is 1.0; #{objects.length} object(s) left unchanged.")
      return true
    end

    scaled = 0
    per_method = Hash.new(0)
    objects.each do |object|
      entry = METHODS.find { |getter, _setter, _label| object.public_send(getter).is_initialized }
      if entry.nil?
        runner.registerWarning("#{object.nameString} has no rate set; skipped.")
        next
      end
      getter, setter, label = entry
      current = object.public_send(getter).get
      object.public_send(setter, current * multiplier)
      per_method[label] += 1
      scaled += 1
    end

    runner.registerInitialCondition("#{objects.length} infiltration object(s) found.")
    runner.registerValue('infiltration_multiplier', multiplier)
    runner.registerFinalCondition(
      "Scaled #{scaled} object(s) by #{multiplier}: " +
      per_method.map { |label, count| "#{count} x #{label}" }.join(', ')
    )
    true
  rescue StandardError => e
    runner.registerError("Set Infiltration Rate failed: #{e.message}")
    false
  end
end

SetInfiltrationRate.new.registerWithApplication
