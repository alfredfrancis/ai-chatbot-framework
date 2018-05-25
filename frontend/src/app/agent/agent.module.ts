import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { FlexLayoutModule } from '@angular/flex-layout';

import { AgentRoutingModule } from './agent-routing.module';
import { IntentsComponent } from './intents/intents.component';

/* Material UI imports begins here */
import {MatIconModule,MatCardModule,MatInputModule,
MatOptionModule,MatSelectModule,MatCheckboxModule,MatButtonModule} from '@angular/material';
import {MatGridListModule} from '@angular/material/grid-list';
import {MatDividerModule} from '@angular/material/divider';
import {MatExpansionModule} from '@angular/material/expansion';
import {MatSliderModule} from '@angular/material/slider';
import {MatChipsModule} from '@angular/material/chips';
import {MatAutocompleteModule} from '@angular/material/autocomplete';

/* Material UI imports ends here */


/* Services imports begins here */
import { IntentService } from '../services/intent.service';
import {TrainingService} from '../services/training.service'
import {IntentResolverService} from '../services/intent-resolver.service';
import {ChatService} from '../services/chat.service'
import {AgentsService} from '../services/agents.service'
import {EntitiesService,EntityResolverService} from '../services/entities.service'
/* Services imports ends here */

import { SettingsComponent } from './settings/settings.component';
import { ChatComponent } from './chat/chat.component'
import { IntentComponent } from './intent/intent.component';
import { TrainComponent } from './train/train.component';

import { AutofocusDirective } from '../directives/autofocus.directive';
import { EntitiesComponent } from './entities/entities.component';
import { EntityComponent } from './entity/entity.component';

@NgModule({
  imports: [
    CommonModule,
    ReactiveFormsModule,
    HttpClientModule,
    FormsModule,
    FlexLayoutModule,
    
    AgentRoutingModule,
    
    MatIconModule,
    MatCardModule,
    MatInputModule,
    MatOptionModule,
    MatSelectModule,
    MatCheckboxModule,
    MatButtonModule,
    MatGridListModule,
    MatDividerModule,
    MatExpansionModule,
    MatSliderModule,
    MatChipsModule,
    MatAutocompleteModule

  ],
  declarations: [IntentsComponent, IntentComponent, TrainComponent, SettingsComponent,
     ChatComponent,AutofocusDirective, EntitiesComponent, EntityComponent],
  providers:[AgentsService,IntentService,
    IntentResolverService,TrainingService,ChatService,EntitiesService,EntityResolverService]
})
export class AgentModule { }
